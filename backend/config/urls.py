from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/storage/", include("apps.storage.urls")),
    path("api/v1/script-optimizer/", include("apps.script_optimizer.urls")),
    path("api/v1/healthz", lambda request: JsonResponse({"ok": True})),
]
