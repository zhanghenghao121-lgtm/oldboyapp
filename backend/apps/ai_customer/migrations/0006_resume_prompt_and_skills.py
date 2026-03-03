from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0005_resumeassistanttask"),
    ]

    operations = [
        migrations.AddField(
            model_name="aicustomersetting",
            name="resume_system_prompt",
            field=models.TextField(
                default=(
                    "你是专业简历顾问。请基于职位名称、OCR识别的岗位要求和技能点分析结果，"
                    "输出结构化、真实可填写的简历草稿。不得虚构具体经历，缺失信息必须标注[待填写]。"
                )
            ),
        ),
        migrations.AddField(
            model_name="resumeassistanttask",
            name="skill_points",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
