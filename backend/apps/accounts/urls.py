from django.urls import path
from .views import email_code, register, captcha, login_view, me, logout_view, reset_password

urlpatterns = [
    path("email-code", email_code),
    path("register", register),
    path("captcha", captcha),
    path("login", login_view),
    path("me", me),
    path("logout", logout_view),
    path("reset-password", reset_password),
]
