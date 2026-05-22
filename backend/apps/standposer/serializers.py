from rest_framework import serializers

from .models import CharacterAsset, GenerationTask, SceneShot, StandScene
from .services import cos_download_url


class CharacterAssetSerializer(serializers.ModelSerializer):
    model_url = serializers.SerializerMethodField()

    def get_model_url(self, obj):
        return cos_download_url(obj.cos_key, obj.model_url)

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
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        data = dict(representation.get("scene_data") or {})
        placements = []
        character_ids = [item.get("characterId") for item in data.get("placements") or []]
        characters = {
            item.id: item
            for item in CharacterAsset.objects.filter(id__in=[value for value in character_ids if value])
        }
        for item in data.get("placements") or []:
            placement = dict(item)
            character = characters.get(placement.get("characterId"))
            if character:
                placement["modelUrl"] = cos_download_url(character.cos_key, character.model_url)
            placements.append(placement)
        data["placements"] = placements
        representation["scene_data"] = data
        if instance.thumbnail_url:
            shot = instance.shots.order_by("-id").first()
            representation["thumbnail_url"] = cos_download_url(shot.cos_key, instance.thumbnail_url) if shot else instance.thumbnail_url
        return representation

    class Meta:
        model = StandScene
        fields = ["id", "name", "scene_data", "thumbnail_url", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SceneShotSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        return cos_download_url(obj.cos_key, obj.image_url)

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
