from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0003_siteconfig"),
    ]

    operations = [
        migrations.AlterField(
            model_name="siteconfig",
            name="key",
            field=models.CharField(
                choices=[
                    ("default_avatar_url", "默认头像URL"),
                    ("storyboard_default_prompt", "剧本分镜默认提示词"),
                    ("paragraph_default_prompt", "段落分镜默认提示词"),
                    ("recharge_wechat_id", "充值页微信号"),
                    ("recharge_qr_url", "充值页二维码URL"),
                ],
                max_length=64,
                unique=True,
            ),
        ),
    ]
