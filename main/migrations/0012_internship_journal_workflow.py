from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0011_internshipoffer_is_archived"),
    ]

    operations = [
        migrations.AddField(
            model_name="internship",
            name="journal_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="internship",
            name="journal_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="internship",
            name="journal_confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="confirmed_journals",
                to="accounts.user",
            ),
        ),
        migrations.AddField(
            model_name="internship",
            name="journal_pdf",
            field=models.FileField(blank=True, null=True, upload_to="journals/"),
        ),
    ]
