from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_alter_pointsusagelog_usage_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_member",
            field=models.BooleanField(default=False),
        ),
    ]
