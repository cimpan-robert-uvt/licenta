from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0003_internship_signed_contract"),
    ]

    operations = [
        migrations.AlterField(
            model_name="journalentry",
            name="validated_by",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"role": "company"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="validated_journals",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
