from rest_framework import serializers
from apps.console.models import SiteConfig


class ConsoleLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)


class SiteConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfig
        fields = ["key", "value", "updated_at"]


class SiteConfigUpdateSerializer(serializers.Serializer):
    value = serializers.CharField(allow_blank=True)
