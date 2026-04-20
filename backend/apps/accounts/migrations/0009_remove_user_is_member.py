from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_user_is_member"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="is_member",
        ),
    ]
