from rest_framework import serializers


class EmailCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    scene = serializers.ChoiceField(choices=["register", "reset"])


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    email = serializers.EmailField()
    email_code = serializers.CharField(max_length=6)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    captcha_id = serializers.CharField(max_length=64)
    captcha_code = serializers.CharField(max_length=8)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    email_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(max_length=128)
