from rest_framework import serializers
from .utils import valid_password, valid_username


class EmailCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    scene = serializers.ChoiceField(choices=["register", "reset"])
    username = serializers.CharField(max_length=20, min_length=3, required=False, allow_blank=False)

    def validate_username(self, value):
        return _validate_username_value(value)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=20, min_length=3)
    password = serializers.CharField(max_length=128)
    email = serializers.EmailField()
    email_code = serializers.CharField(max_length=6)

    def validate_username(self, value):
        return _validate_username_value(value)

    def validate_password(self, value):
        return _validate_password_value(value)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    captcha_id = serializers.CharField(max_length=64)
    captcha_code = serializers.CharField(max_length=8)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    email_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(max_length=128)

    def validate_new_password(self, value):
        return _validate_password_value(value)


def _validate_username_value(value: str):
    username = value.strip()
    if not valid_username(username):
        raise serializers.ValidationError("用户名只能包含字母、数字或下划线，长度3-20位")
    return username


def _validate_password_value(value: str):
    if not valid_password(value):
        raise serializers.ValidationError("密码必须至少8位，且包含大小写字母和数字")
    return value
