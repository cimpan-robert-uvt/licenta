from django.db import migrations, models
import django.contrib.auth.validators


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_cleanup_unsupported_roles"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                error_messages={"unique": "Un utilizator cu acest nume există deja."},
                help_text="30 de caractere sau mai puțin. Doar litere, cifre și @/./+/-/_ .",
                max_length=30,
                unique=True,
                validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                verbose_name="username",
            ),
        ),
    ]
