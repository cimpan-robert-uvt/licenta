from datetime import timedelta

from django.db import models
from django.utils import timezone
from accounts.models import User


class InternshipOffer(models.Model):
    company = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "company"},
        related_name="internship_offers",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    duration_weeks = models.IntegerField(default=12)
    start_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ofertă de stagiu"
        verbose_name_plural = "Oferte de stagiu"

    def __str__(self):
        return f"{self.title} - {self.company.company_profile.company_name}"


class Application(models.Model):
    STATUS_CHOICES = [
        ("pending", "În așteptare"),
        ("hr_accepted", "Acceptat - așteaptă confirmarea studentului"),
        ("rejected", "Respins"),
        ("student_declined", "Refuzată de student"),
        ("student_confirmed", "Confirmată de student"),
        ("withdrawn", "Retrasă automat"),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "student"},
        related_name="applications",
    )
    offer = models.ForeignKey(
        InternshipOffer, on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "offer")
        ordering = ["-applied_at"]
        verbose_name = "Aplicație"
        verbose_name_plural = "Aplicații"

    def __str__(self):
        return f"{self.student.get_full_name()} -> {self.offer.title}"

    def accept(self):
        if self.status != "pending":
            raise ValueError(
                f"Nu se poate accepta aplicația cu statusul '{self.status}'"
            )

        self.status = "hr_accepted"
        self.save()

    def reject(self):
        if self.status != "pending":
            raise ValueError(
                f"Nu se poate respinge aplicația cu statusul '{self.status}'"
            )
        self.status = "rejected"
        self.save()


class CompatibilityMatch(models.Model):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "student"},
        related_name="compatibility_matches",
    )
    offer = models.ForeignKey(
        InternshipOffer,
        on_delete=models.CASCADE,
        related_name="compatibility_matches",
    )
    score = models.IntegerField()
    explanation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score"]
        verbose_name = "Potrivire compatibilitate"
        verbose_name_plural = "Potriviri compatibilitate"

    def __str__(self):
        return f"{self.student.get_full_name()} ↔ {self.offer.title} ({self.score})"


class Internship(models.Model):
    offer = models.ForeignKey(
        InternshipOffer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="internships",
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "student"},
        related_name="internships",
    )
    company = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "company"},
        related_name="hosted_internships",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    signed_contract = models.FileField(upload_to="contracts/", null=True, blank=True)
    journal_submitted_at = models.DateTimeField(null=True, blank=True)
    journal_confirmed_at = models.DateTimeField(null=True, blank=True)
    journal_confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_journals",
    )
    journal_pdf = models.FileField(upload_to="journals/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    mentor_name = models.CharField(max_length=255, blank=True, null=True)
    mentor_email = models.EmailField(blank=True, null=True)
    mentor_phone = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Stagiu de practică"
        verbose_name_plural = "Stagii de practică"

    def __str__(self):
        title = (
            self.offer.title
            if self.offer
            else self.company.company_profile.company_name
        )
        return f"{self.student.get_full_name()} la {title}"

    def get_status(self):
        today = timezone.now().date()
        if today < self.start_date:
            return "not_started"

        if self.journal_confirmed_at:
            return "completed"

        planned_end = self.get_planned_end_date()
        end_check = planned_end or self.end_date
        if end_check and today > end_check:
            return "practica_finalizata"

        return "in_progress"

    def get_days_until_start(self):
        """Days remaining until internship starts"""
        if self.get_status() == "not_started":
            return (self.start_date - timezone.now().date()).days
        return None

    def get_planned_end_date(self):
        if self.offer:
            return self.start_date + timedelta(weeks=self.offer.duration_weeks)
        return self.end_date

    def journal_required_weeks(self):
        if self.offer and self.offer.duration_weeks:
            return self.offer.duration_weeks
        return 0

    def journal_is_complete(self):
        required_weeks = self.journal_required_weeks()
        if not required_weeks:
            return False
        return self.journal_entries.count() >= required_weeks

    def journal_is_locked(self):
        return bool(self.journal_submitted_at or self.journal_confirmed_at)

    def journal_can_be_submitted(self):
        return self.journal_is_complete() and not self.journal_is_locked()

    def journal_is_confirmed(self):
        return bool(self.journal_confirmed_at)

    def get_current_week(self):
        if not self.is_active or self.get_status() != "in_progress":
            return None
        days_elapsed = (timezone.now().date() - self.start_date).days
        current_week = (days_elapsed // 7) + 1

        if self.offer and self.offer.duration_weeks:
            current_week = min(current_week, self.offer.duration_weeks)

        return current_week

    def end_internship(self):
        self.is_active = False
        self.end_date = timezone.now().date()
        self.save()


class JournalEntry(models.Model):
    internship = models.ForeignKey(
        Internship, on_delete=models.CASCADE, related_name="journal_entries"
    )
    week_number = models.IntegerField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "internship",
            "week_number",
        )
        ordering = ["-week_number"]
        verbose_name = "Intrare în jurnal"
        verbose_name_plural = "Intrări în jurnal"

    def __str__(self):
        return (
            f"Săptămâna {self.week_number} - {self.internship.student.get_full_name()}"
        )


class CareerAnalysis(models.Model):
    internship = models.ForeignKey(
        Internship, on_delete=models.CASCADE, related_name="career_analysis"
    )
    result_text = models.TextField()
    user_context = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Analiză de carieră"
        verbose_name_plural = "Analize de carieră"

    def __str__(self):
        return f"Analiză carieră - {self.internship.student.get_full_name()}"
