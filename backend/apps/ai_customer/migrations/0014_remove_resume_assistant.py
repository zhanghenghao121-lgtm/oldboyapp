from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0013_alter_aibloggerpost_status_text_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="aicustomersetting",
            name="resume_system_prompt",
        ),
        migrations.DeleteModel(
            name="ResumeAssistantTask",
        ),
    ]
