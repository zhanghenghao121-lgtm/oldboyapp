import uuid
from django.core.cache import cache
from django.contrib.auth import get_user_model

User = get_user_model()
CONSOLE_TOKEN_TTL = 7 * 24 * 3600
CONSOLE_TOKEN_HEADER = "HTTP_X_CONSOLE_TOKEN"


def issue_console_token(user_id: int) -> str:
    token = uuid.uuid4().hex
    cache.set(f"console_token:{token}", user_id, CONSOLE_TOKEN_TTL)
    return token


def revoke_console_token(token: str):
    if token:
        cache.delete(f"console_token:{token}")


def resolve_console_user(request):
    token = request.META.get(CONSOLE_TOKEN_HEADER, "").strip()
    if token:
        user_id = cache.get(f"console_token:{token}")
        if user_id:
            user = User.objects.filter(id=user_id, is_staff=True, is_active=True).first()
            if user:
                return user, token
    user = request.user
    if user and user.is_authenticated and user.is_staff:
        return user, ""
    return None, token
