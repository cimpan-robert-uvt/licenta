from datetime import date

from django.test import TestCase

from accounts.models import User, CompanyProfile
from main.models import InternshipOffer, Internship, Application


class InternshipModelTests(TestCase):
    def setUp(self):
        self.company = User.objects.create_user(
            username="comp",
            email="comp@example.com",
            password="Testpass123!",
            first_name="Comp",
            last_name="Any",
            role="company",
            phone_number="0790000000",
            birth_date=date(1990, 1, 1),
        )
        CompanyProfile.objects.create(user=self.company, company_name="C", domain="informatica")

        self.student = User.objects.create_user(
            username="stud",
            email="stud@example.com",
            password="Testpass123!",
            first_name="Stu",
            last_name="Dent",
            role="student",
            phone_number="0710000000",
            birth_date=date(2000, 1, 1),
        )

    def test_get_current_week_in_progress_returns_expected_week(self):
        from django.utils import timezone

        offer = InternshipOffer.objects.create(
            company=self.company,
            title="T1",
            description="d",
            duration_weeks=12,
            start_date=(timezone.now().date() - timezone.timedelta(days=8)),
            is_active=True,
        )

        internship = Internship.objects.create(
            student=self.student,
            company=self.company,
            offer=offer,
            start_date=offer.start_date,
            is_active=True,
        )

        current_week = internship.get_current_week()
        self.assertEqual(current_week, 2)

    def test_get_current_week_none_when_not_in_progress(self):
        from django.utils import timezone

        offer = InternshipOffer.objects.create(
            company=self.company,
            title="T2",
            description="d",
            duration_weeks=4,
            start_date=(timezone.now().date() + timezone.timedelta(days=10)),
            is_active=True,
        )

        internship = Internship.objects.create(
            student=self.student,
            company=self.company,
            offer=offer,
            start_date=offer.start_date,
            is_active=True,
        )

        self.assertIsNone(internship.get_current_week())


class ApplicationModelTests(TestCase):
    def setUp(self):
        self.company = User.objects.create_user(
            username="comp2",
            email="comp2@example.com",
            password="Testpass123!",
            first_name="Comp2",
            last_name="Any",
            role="company",
            phone_number="0791111111",
            birth_date=date(1990, 1, 1),
        )
        CompanyProfile.objects.create(user=self.company, company_name="C2", domain="informatica")

        self.student = User.objects.create_user(
            username="stud2",
            email="stud2@example.com",
            password="Testpass123!",
            first_name="Stu2",
            last_name="Dent2",
            role="student",
            phone_number="0711111111",
            birth_date=date(2000, 1, 1),
        )

        self.offer = InternshipOffer.objects.create(
            company=self.company,
            title="Offer",
            description="d",
            duration_weeks=8,
            is_active=True,
        )

    def test_accept_changes_status_and_raises_on_non_pending(self):
        app = Application.objects.create(student=self.student, offer=self.offer, status="pending")
        app.accept()
        app.refresh_from_db()
        self.assertEqual(app.status, "hr_accepted")

        with self.assertRaises(ValueError):
            app.accept()

    def test_reject_changes_status_and_raises_on_non_pending(self):
        app = Application.objects.create(student=self.student, offer=self.offer, status="pending")
        app.reject()
        app.refresh_from_db()
        self.assertEqual(app.status, "rejected")

        with self.assertRaises(ValueError):
            app.reject()
