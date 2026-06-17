from decimal import Decimal

from rest_framework import serializers
from apps.accounts.utils import valid_username
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


class ConsoleUserUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=20, min_length=3, required=False)
    email = serializers.EmailField(required=False)
    avatar_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    signature = serializers.CharField(max_length=120, required=False, allow_blank=True)
    points = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False)
    is_active = serializers.BooleanField(required=False)
    is_whitelisted = serializers.BooleanField(required=False)
    can_access_workbench = serializers.BooleanField(required=False)
    can_access_storyboard = serializers.BooleanField(required=False)

    def validate_username(self, value):
        username = value.strip()
        if not valid_username(username):
            raise serializers.ValidationError("用户名只能包含字母、数字或下划线，长度3-20位")
        return username
