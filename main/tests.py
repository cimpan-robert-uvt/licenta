from datetime import date
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.urls import reverse

from accounts.forms import ProfileForm
from accounts.models import User, StudentProfile, CompanyProfile


from .utils_api import _clamp_score, _compute_weighted_score, _extract_json_text


class UtilsApiTests(TestCase):
    def test_extract_json_text_handles_markdown_fenced_json_with_extra_text(self):
        raw_text = (
            "Răspuns Gemini:\n"
            "```json\n"
            '{"scor": 90, "justificare": "Potrivire bună"}\n'
            "```\n"
            "Text adițional după JSON."
        )

        extracted = _extract_json_text(raw_text)

        self.assertEqual(
            extracted,
            '{"scor": 90, "justificare": "Potrivire bună"}',
        )

    def test_compute_weighted_score_with_all_subscores_maxed_returns_100(self):
        item = {
            "skills_match": 100,
            "experience_match": 100,
            "education_match": 100,
        }

        score = _compute_weighted_score(item)

        self.assertEqual(score, 100)

    def test_compute_weighted_score_with_missing_subscore_uses_available_components(
        self,
    ):
        item = {
            "skills_match": 100,
            "experience_match": 80,
        }

        score = _compute_weighted_score(item)

        self.assertEqual(score, 74)

    def test_clamp_score_limits_values_above_100(self):
        self.assertEqual(_clamp_score(150), 100)


class ProfileNotificationTests(TestCase):
    def test_student_profile_form_saves_notification_preference(self):
        student = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="Testpass123!",
            first_name="Ana",
            last_name="Pop",
            role="student",
            phone_number="0712345678",
            birth_date=date(2000, 1, 1),
        )
        StudentProfile.objects.create(user=student, domain="informatica")

        form = ProfileForm(
            data={
                "username": student.username,
                "email": student.email,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "phone_number": student.phone_number,
                "birth_date": "2000-01-01",
                "domain": "informatica",
                "receive_offer_notifications": "on",
            },
            instance=student,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        student.refresh_from_db()
        self.assertTrue(student.student_profile.receive_offer_notifications)


class NewOfferNotificationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.company = User.objects.create_user(
            username="company1",
            email="company@example.com",
            password="Testpass123!",
            first_name="Comp",
            last_name="Any",
            role="company",
            phone_number="0798765432",
            birth_date=date(1995, 5, 5),
        )
        CompanyProfile.objects.create(
            user=self.company,
            company_name="Firma Test",
            domain="informatica",
        )

    @patch("main.views.send_mail")
    def test_create_internship_offer_notifies_only_opted_in_students_in_same_domain(
        self, send_mail_mock
    ):
        student1 = User.objects.create_user(
            username="s1",
            email="s1@example.com",
            password="Testpass123!",
            first_name="S1",
            last_name="User",
            role="student",
            phone_number="0711111111",
            birth_date=date(2000, 1, 1),
        )
        StudentProfile.objects.create(
            user=student1,
            domain="informatica",
            receive_offer_notifications=True,
        )

        student2 = User.objects.create_user(
            username="s2",
            email="s2@example.com",
            password="Testpass123!",
            first_name="S2",
            last_name="User",
            role="student",
            phone_number="0722222222",
            birth_date=date(2000, 2, 2),
        )
        StudentProfile.objects.create(
            user=student2,
            domain="informatica",
            receive_offer_notifications=True,
        )

        student3 = User.objects.create_user(
            username="s3",
            email="s3@example.com",
            password="Testpass123!",
            first_name="S3",
            last_name="User",
            role="student",
            phone_number="0733333333",
            birth_date=date(2000, 3, 3),
        )
        StudentProfile.objects.create(
            user=student3,
            domain="informatica",
            receive_offer_notifications=False,
        )

        student4 = User.objects.create_user(
            username="s4",
            email="s4@example.com",
            password="Testpass123!",
            first_name="S4",
            last_name="User",
            role="student",
            phone_number="0744444444",
            birth_date=date(2000, 4, 4),
        )
        StudentProfile.objects.create(
            user=student4,
            domain="economie",
            receive_offer_notifications=True,
        )

        self.client.force_login(self.company)
        response = self.client.post(
            reverse("create_internship_offer"),
            data={
                "title": "Ofertă nouă",
                "description": "Descriere ofertă",
                "requirements": "Cerințe",
                "location": "Cluj-Napoca",
                "duration_weeks": 12,
                "start_date": date.today().isoformat(),
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(send_mail_mock.call_count, 2)
        recipient_emails = [call.args[3][0] for call in send_mail_mock.call_args_list]
        self.assertCountEqual(recipient_emails, ["s1@example.com", "s2@example.com"])
