from django.urls import path

from .views import character_detail, character_generate_model, characters, scene_detail, scenes, shots

urlpatterns = [
    path("standposer/characters/", characters),
    path("standposer/characters/<int:character_id>/", character_detail),
    path("standposer/characters/<int:character_id>/generate-model/", character_generate_model),
    path("standposer/scenes/", scenes),
    path("standposer/scenes/<int:scene_id>/", scene_detail),
    path("standposer/shots/", shots),
]
