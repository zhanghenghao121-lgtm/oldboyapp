from django.urls import path

from apps.ai_customer.views import (
    ai_manga_config,
    ai_manga_scenes,
    ai_manga_storyboard,
)

urlpatterns = [
    path("ai-manga/config", ai_manga_config),
    path("ai-manga/scenes", ai_manga_scenes),
    path("ai-manga/storyboard", ai_manga_storyboard),
]
