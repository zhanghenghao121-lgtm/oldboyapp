from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.console.models import SiteBackground

User = get_user_model()


class ConsoleLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)


class SiteBackgroundSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteBackground
        fields = ["scene", "image_url", "updated_at"]


class BackgroundUpdateSerializer(serializers.Serializer):
    image_url = serializers.URLField(max_length=500, allow_blank=True)


class ConsoleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "avatar_url", "signature", "is_active", "date_joined", "last_login"]


class ConsoleUserUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    avatar_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    signature = serializers.CharField(max_length=120, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError("用户名不能为空")
        qs = User.objects.filter(username=username)
        if self.context.get("user_id"):
            qs = qs.exclude(id=self.context["user_id"])
        if qs.exists():
            raise serializers.ValidationError("用户名已存在")
        return username

    def validate_email(self, value):
        email = value.lower()
        qs = User.objects.filter(email=email)
        if self.context.get("user_id"):
            qs = qs.exclude(id=self.context["user_id"])
        if qs.exists():
            raise serializers.ValidationError("邮箱已存在")
        return email
