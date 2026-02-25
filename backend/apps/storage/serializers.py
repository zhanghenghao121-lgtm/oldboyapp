from rest_framework import serializers


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    folder = serializers.CharField(required=False, allow_blank=True, default="uploads")
