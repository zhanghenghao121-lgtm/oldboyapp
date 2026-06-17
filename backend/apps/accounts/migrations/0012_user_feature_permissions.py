from django.db import migrations, models


def migrate_existing_permissions(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(
        models.Q(is_whitelisted=True) | models.Q(is_staff=True) | models.Q(is_superuser=True)
    ).update(can_access_workbench=True, can_access_storyboard=True)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_user_is_whitelisted"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_access_workbench",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="can_access_storyboard",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(migrate_existing_permissions, migrations.RunPython.noop),
    ]
