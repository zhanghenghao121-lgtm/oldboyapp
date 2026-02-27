from django.urls import path
from .views import paragraph_storyboard, ping, storyboard

urlpatterns = [
    path("ping", ping),
    path("storyboard", storyboard),
    path("paragraph-storyboard", paragraph_storyboard),
]
