import uuid
from django.core.cache import cache
from django.core import signing
from django.contrib.auth import get_user_model

User = get_user_model()
CONSOLE_TOKEN_TTL = 7 * 24 * 3600
CONSOLE_TOKEN_HEADER = "HTTP_X_CONSOLE_TOKEN"
CONSOLE_TOKEN_SALT = "oldboy-console-token"


def _signer():
    return signing.TimestampSigner(salt=CONSOLE_TOKEN_SALT)


def _authorization_token(request) -> str:
    value = request.META.get("HTTP_AUTHORIZATION", "").strip()
    if not value:
        return ""
    parts = value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() in {"bearer", "token"}:
        return parts[1].strip()
    return value


def issue_console_token(user_id: int) -> str:
    nonce = uuid.uuid4().hex
    token = _signer().sign(f"{user_id}:{nonce}")
    cache.set(f"console_token:{token}", user_id, CONSOLE_TOKEN_TTL)
    return token


def revoke_console_token(token: str):
    if token:
        cache.delete(f"console_token:{token}")
        cache.set(f"console_token_revoked:{token}", "1", CONSOLE_TOKEN_TTL)


def _resolve_signed_token(token: str):
    try:
        if cache.get(f"console_token_revoked:{token}"):
            return None
        value = _signer().unsign(token, max_age=CONSOLE_TOKEN_TTL)
        user_id = int(str(value).split(":", 1)[0])
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        return None
    return User.objects.filter(id=user_id, is_staff=True, is_active=True).first()


def resolve_console_user(request):
    token = request.META.get(CONSOLE_TOKEN_HEADER, "").strip() or _authorization_token(request)
    if token:
        user_id = cache.get(f"console_token:{token}")
        if user_id:
            user = User.objects.filter(id=user_id, is_staff=True, is_active=True).first()
            if user:
                return user, token
        user = _resolve_signed_token(token)
        if user:
            return user, token
    user = request.user
    if user and user.is_authenticated and user.is_staff:
        return user, ""
    return None, token
