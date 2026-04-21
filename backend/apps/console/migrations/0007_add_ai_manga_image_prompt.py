from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0006_alter_siteconfig_key_model_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="siteconfig",
            name="key",
            field=models.CharField(
                choices=[
                    ("default_avatar_url", "默认头像URL"),
                    ("recharge_wechat_id", "充值页微信号"),
                    ("recharge_qr_url", "充值页二维码URL"),
                    ("ai_assistant_base_url", "助手模型API地址"),
                    ("ai_assistant_api_key", "助手模型API Key"),
                    ("ai_assistant_model", "助手模型名称"),
                    ("ai_manga_base_url", "漫剧模型API地址"),
                    ("ai_manga_api_key", "漫剧模型API Key"),
                    ("ai_manga_model", "漫剧模型名称"),
                    ("ai_manga_storyboard_prompt", "AI漫剧分镜提示词"),
                    ("ai_manga_image_prompt", "AI漫剧分镜图提示词"),
                ],
                max_length=64,
                unique=True,
            ),
        ),
    ]
