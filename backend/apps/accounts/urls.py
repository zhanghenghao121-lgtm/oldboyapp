from django.urls import path
from .views import (
    email_code,
    register,
    captcha,
    energy_slider,
    energy_slider_verify,
    login_view,
    me,
    points_logs,
    profile_update,
    logout_view,
    reset_password,
    change_password,
)

urlpatterns = [
    path("email-code", email_code),
    path("register", register),
    path("captcha", captcha),
    path("energy-slider", energy_slider),
    path("energy-slider/verify", energy_slider_verify),
    path("login", login_view),
    path("me", me),
    path("points-logs", points_logs),
    path("profile", profile_update),
    path("logout", logout_view),
    path("reset-password", reset_password),
    path("change-password", change_password),
]
