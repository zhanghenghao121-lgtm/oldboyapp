from django.db import migrations, models


def whitelist_admins(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(models.Q(is_staff=True) | models.Q(is_superuser=True)).update(is_whitelisted=True)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_alter_pointsusagelog_usage_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_whitelisted",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(whitelist_admins, migrations.RunPython.noop),
    ]
