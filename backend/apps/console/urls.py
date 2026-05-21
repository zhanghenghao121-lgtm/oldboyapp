from django.urls import path

from apps.console.views import (
    console_config_update,
    console_configs,
    console_login,
    console_logout,
    console_me,
    public_backgrounds,
)

urlpatterns = [
    path("site/backgrounds", public_backgrounds),
    path("console/login", console_login),
    path("console/me", console_me),
    path("console/logout", console_logout),
    path("console/configs", console_configs),
    path("console/configs/<str:key>", console_config_update),
]
