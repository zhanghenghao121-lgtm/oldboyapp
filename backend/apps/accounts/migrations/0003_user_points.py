from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_avatar_url_user_signature"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="points",
            field=models.DecimalField(decimal_places=2, default=50, max_digits=12),
        ),
    ]
