from django.db import migrations


def remove_script_optimizer_legacy(apps, schema_editor):
    SiteBackground = apps.get_model("console", "SiteBackground")
    SiteConfig = apps.get_model("console", "SiteConfig")

    SiteBackground.objects.filter(scene="script_optimizer").delete()
    SiteConfig.objects.filter(
        key__in=["storyboard_default_prompt", "paragraph_default_prompt"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0004_alter_siteconfig_key"),
    ]

    operations = [
        migrations.RunPython(
            remove_script_optimizer_legacy,
            migrations.RunPython.noop,
        ),
    ]
