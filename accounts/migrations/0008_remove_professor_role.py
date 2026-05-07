from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "accounts",
            "0007_alter_cveducation_options_alter_cvexperience_options_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("student", "Student"),
                    ("company", "Companie"),
                ],
                default="student",
                max_length=20,
            ),
        ),
    ]
