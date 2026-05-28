from django.urls import path
from .views import file, upload

urlpatterns = [
    path("upload", upload),
    path("file", file),
]
