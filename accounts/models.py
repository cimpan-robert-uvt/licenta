from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from datetime import date


DOMAIN_CHOICES = [
    ("agricultura", "Agricultură"),
    ("altele", "Altele"),
    ("arhitectura", "Arhitectură"),
    ("arte", "Arte"),
    ("biotehnologie", "Biotehnologie"),
    ("chimie", "Chimie"),
    ("comunicare", "Comunicare"),
    ("constructii", "Construcții"),
    ("drept", "Drept"),
    ("educatie", "Educație"),
    ("electronica", "Electronică"),
    ("economie", "Economie"),
    ("farmacie", "Farmacie"),
    ("finante", "Finanțe"),
    ("fizica", "Fizică"),
    ("informatica", "Informatică"),
    ("inginerie", "Inginerie"),
    ("jurnalism", "Jurnalism"),
    ("management", "Management"),
    ("marketing", "Marketing"),
    ("mecanica", "Mecanică"),
    ("medicina", "Medicină"),
    ("medicina_dentara", "Medicină dentară"),
    ("psihologie", "Psihologie"),
    ("turism", "Turism"),
]

STUDY_LEVEL_CHOICES = [
    ("licenta", "Licenta"),
    ("master", "Master"),
]


class User(AbstractUser):
    username_validator = UnicodeUsernameValidator()

    ROLE_CHOICES = [
        ("student", "Student"),
        ("company", "Companie"),
    ]

    username = models.CharField(
        "username",
        max_length=30,
        unique=True,
        help_text="30 de caractere sau mai puțin. Doar litere, cifre și @/./+/-/_ .",
        validators=[username_validator],
        error_messages={
            "unique": "Un utilizator cu acest nume există deja.",
        },
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="student")
    phone_number = models.CharField(max_length=15, blank=False, null=True, default=None)
    birth_date = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", null=True, blank=True
    )

    def clean(self):
        super().clean()
        if self.birth_date and self.birth_date > date.today():
            raise ValidationError(
                {"birth_date": "Data nașterii nu poate fi în viitor."}
            )

    class Meta:
        db_table = "auth_user"
        verbose_name = "Utilizator"
        verbose_name_plural = "Utilizatori"

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    def is_student(self):
        return self.role == "student"

    def is_company(self):
        return self.role == "company"


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    cnp = models.CharField(max_length=13, blank=True)
    faculty = models.CharField(max_length=255, blank=True)
    domain = models.CharField(max_length=50, choices=DOMAIN_CHOICES, default="altele")
    receive_offer_notifications = models.BooleanField(default=False)
    specialization = models.CharField(max_length=255, blank=True)
    year_of_study = models.IntegerField(null=True, blank=True)
    study_level = models.CharField(max_length=20, choices=STUDY_LEVEL_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Profil student"
        verbose_name_plural = "Profile studenți"

    def __str__(self):
        return f"Profil {self.user.get_full_name()}"


class CompanyProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="company_profile"
    )
    company_name = models.CharField(max_length=255)
    full_company_name = models.CharField(max_length=255, blank=True)
    cui = models.CharField(max_length=30, blank=True)
    domain = models.CharField(max_length=50, choices=DOMAIN_CHOICES, default="altele")
    industry = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    address = models.TextField(blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Profil companie"
        verbose_name_plural = "Profile companii"

    def __str__(self):
        return self.company_name


class StudentCV(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_cv"
    )
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    linkedin = models.URLField(blank=True)
    city = models.CharField(max_length=100, blank=True)

    resume = models.TextField(max_length=500)

    pdf_file = models.FileField(upload_to="cv/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CV Student"
        verbose_name_plural = "CV Studenți"

    def __str__(self):
        return f"CV - {self.user.get_full_name()}"


class CVEducation(models.Model):
    cv = models.ForeignKey(
        StudentCV, on_delete=models.CASCADE, related_name="education"
    )
    school_name = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Educație CV"
        verbose_name_plural = "Educații CV"
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.school_name} ({self.start_year}-{self.end_year})"


class CVExperience(models.Model):
    cv = models.ForeignKey(
        StudentCV, on_delete=models.CASCADE, related_name="experience"
    )
    institution_name = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Experiență CV"
        verbose_name_plural = "Experiențe CV"
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.institution_name} ({self.start_year}-{self.end_year})"


class CVSkill(models.Model):
    SKILL_TYPE_CHOICES = [
        ("program", "Program/Software"),
        ("language", "Limbaj de programare"),
        ("foreign_language", "Limbă străină"),
        ("soft_skill", "Soft Skill"),
    ]

    cv = models.ForeignKey(StudentCV, on_delete=models.CASCADE, related_name="skills")
    skill_type = models.CharField(max_length=20, choices=SKILL_TYPE_CHOICES, blank=True)
    skill_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abilitate CV"
        verbose_name_plural = "Abilități CV"
        ordering = ["skill_type", "skill_name"]

    def __str__(self):
        return f"{self.get_skill_type_display()} - {self.skill_name}"
