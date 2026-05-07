from django.db import migrations


def remove_unsupported_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.exclude(role__in=["student", "company"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_remove_professor_role"),
    ]

    operations = [
        migrations.RunPython(remove_unsupported_roles, migrations.RunPython.noop),
    ]
