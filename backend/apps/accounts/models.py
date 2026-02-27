from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    avatar_url = models.URLField(max_length=500, blank=True, default="")
    signature = models.CharField(max_length=120, blank=True, default="")
