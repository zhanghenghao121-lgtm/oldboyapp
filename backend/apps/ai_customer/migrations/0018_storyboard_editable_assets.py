from django.db import migrations, models


def remove_legacy_asset_types(apps, schema_editor):
    StoryboardAsset = apps.get_model("ai_customer", "StoryboardAsset")
    StoryboardAsset.objects.filter(asset_type__in=["costume", "style"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ai_customer", "0017_storyboard_models"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_asset_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="storyboardasset",
            name="asset_type",
            field=models.CharField(
                choices=[("character", "人物"), ("scene", "场景"), ("prop", "道具")],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="storyboardasset",
            name="image_url",
            field=models.URLField(blank=True, default="", max_length=1000),
        ),
    ]
