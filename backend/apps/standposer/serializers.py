from rest_framework import serializers

from .models import CharacterAsset, GenerationTask, SceneShot, StandScene


class CharacterAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CharacterAsset
        fields = [
            "id",
            "name",
            "model_url",
            "cos_key",
            "file_size",
            "content_type",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "model_url", "cos_key", "file_size", "content_type", "created_at", "updated_at"]


class CharacterCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    file = serializers.FileField()


class StandSceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = StandScene
        fields = ["id", "name", "scene_data", "thumbnail_url", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SceneShotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SceneShot
        fields = ["id", "scene", "image_url", "cos_key", "width", "height", "camera_state", "created_at"]
        read_only_fields = ["id", "image_url", "cos_key", "created_at"]


class SceneShotCreateSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField(required=False, allow_null=True)
    image = serializers.FileField()
    width = serializers.IntegerField(min_value=1, required=False)
    height = serializers.IntegerField(min_value=1, required=False)
    camera_state = serializers.CharField(required=False, allow_blank=True)


class GenerationTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationTask
        fields = [
            "id",
            "character",
            "celery_task_id",
            "status",
            "input_payload",
            "result_payload",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
