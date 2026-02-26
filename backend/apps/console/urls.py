from django.urls import path

from apps.console.views import (
    console_background_update,
    console_backgrounds,
    console_login,
    console_logout,
    console_me,
    console_user_update,
    console_users,
    public_backgrounds,
)

urlpatterns = [
    path("site/backgrounds", public_backgrounds),
    path("console/login", console_login),
    path("console/me", console_me),
    path("console/logout", console_logout),
    path("console/backgrounds", console_backgrounds),
    path("console/backgrounds/<str:scene>", console_background_update),
    path("console/users", console_users),
    path("console/users/<int:user_id>", console_user_update),
]
