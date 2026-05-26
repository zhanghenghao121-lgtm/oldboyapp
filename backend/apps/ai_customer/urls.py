from django.urls import path

from apps.ai_customer.views import (
    ai_image_cutout,
    ai_image_cutout_asset,
    ai_image_config,
    ai_image_generate,
    ai_image_task,
    ai_manga_config,
    ai_manga_position_recognize,
    ai_manga_position_reverse_prompt,
    ai_manga_storyboard,
)

urlpatterns = [
    path("ai-manga/config", ai_manga_config),
    path("ai-manga/storyboard", ai_manga_storyboard),
    path("ai-manga/position/recognize", ai_manga_position_recognize),
    path("ai-manga/position/reverse-prompt", ai_manga_position_reverse_prompt),
    path("ai-image/config", ai_image_config),
    path("ai-image/generate", ai_image_generate),
    path("ai-image/cutout", ai_image_cutout),
    path("ai-image/cutout-asset", ai_image_cutout_asset),
    path("ai-image/tasks/<str:task_id>", ai_image_task),
]
