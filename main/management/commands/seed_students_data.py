from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import StudentProfile, User

PASSWORD = "Robi1234!!!"
STUDENT_START_NUMBER = 101
STUDENT_COUNT = 10
STUDENT_DOMAIN = "informatica"
STUDENT_PHONE = "0760999192"
STUDENT_BIRTH_DATE = date(1998, 4, 20)


class Command(BaseCommand):
    help = "Populeaza baza de date doar cu 10 studenti din domeniul Informatica."

    @transaction.atomic
    def handle(self, *args, **options):
        created_students = 0
        updated_students = 0

        for offset in range(STUDENT_COUNT):
            student_number = STUDENT_START_NUMBER + offset
            username = f"robert_student{student_number}"
            email = f"cimpan.robert.tamas+s{student_number}@gmail.com"

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "role": "student",
                    "first_name": "Robert",
                    "last_name": f"Student{student_number}",
                    "phone_number": STUDENT_PHONE,
                    "birth_date": STUDENT_BIRTH_DATE,
                },
            )

            user.email = email
            user.role = "student"
            user.first_name = "Robert"
            user.last_name = f"Student{student_number}"
            user.phone_number = STUDENT_PHONE
            user.birth_date = STUDENT_BIRTH_DATE
            user.set_password(PASSWORD)
            user.save()

            StudentProfile.objects.update_or_create(
                user=user,
                defaults={
                    "domain": STUDENT_DOMAIN,
                },
            )

            if created:
                created_students += 1
            else:
                updated_students += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Seed studenti finalizat. "
                f"Creati: {created_students}, actualizati: {updated_students}."
            )
        )
