from pathlib import Path
import os
import pymysql
import environ

pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(
    DJANGO_DEBUG=(bool, True),
    DB_ENGINE=(str, "sqlite"),
    ALLOWED_HOSTS=(list, ["*"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    DB_HOST=(str, "127.0.0.1"),
    DB_PORT=(str, "3306"),
    DB_NAME=(str, "oldboya"),
    DB_USER=(str, "zhh"),
    DB_PASSWORD=(str, ""),
    REDIS_HOST=(str, "127.0.0.1"),
    REDIS_PORT=(str, "6379"),
    REDIS_PASSWORD=(str, ""),
)

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-secret")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "apps.accounts",
    "apps.storage",
    "apps.script_optimizer",
    "apps.console",
    "apps.ai_customer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if env("DB_ENGINE") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT"),
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

redis_password = env("REDIS_PASSWORD", default="")
redis_auth = f":{redis_password}@" if redis_password else ""
redis_url = f"redis://{redis_auth}{env('REDIS_HOST')}:{env('REDIS_PORT')}/0"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": redis_url,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
        },
        "TIMEOUT": 300,
    }
}

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.common.authentication.CsrfExemptSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("SMTP_HOST", default="smtp.163.com")
EMAIL_PORT = env.int("SMTP_PORT", default=465)
EMAIL_HOST_USER = env("SMTP_USER", default="")
EMAIL_HOST_PASSWORD = env("SMTP_PASS", default="")
EMAIL_USE_SSL = True
DEFAULT_FROM_EMAIL = env("SMTP_FROM", default=EMAIL_HOST_USER)

COS_SECRET_ID = env("COS_SECRET_ID", default="")
COS_SECRET_KEY = env("COS_SECRET_KEY", default="")
COS_BUCKET = env("COS_BUCKET", default="")
COS_REGION = env("COS_REGION", default="")
COS_BASE_URL = env("COS_BASE_URL", default="")

UPLOAD_LIMIT_10MB = 10 * 1024 * 1024
MAX_UPLOAD_SIZE = min(env.int("MAX_UPLOAD_SIZE", default=UPLOAD_LIMIT_10MB), UPLOAD_LIMIT_10MB)
IMAGE_UPLOAD_MAX_EDGE = env.int("IMAGE_UPLOAD_MAX_EDGE", default=2048)
IMAGE_UPLOAD_QUALITY = env.int("IMAGE_UPLOAD_QUALITY", default=82)
UPLOAD_RATE_LIMIT_PER_MINUTE = env.int("UPLOAD_RATE_LIMIT_PER_MINUTE", default=30)
UPLOAD_AUDIT_LOG_ENABLED = env.bool("UPLOAD_AUDIT_LOG_ENABLED", default=True)
EMAIL_CODE_DAILY_LIMIT = env.int("EMAIL_CODE_DAILY_LIMIT", default=10)
DEFAULT_AVATAR_URL = env("DEFAULT_AVATAR_URL", default=f"{COS_BASE_URL}/images/octopus-default.png" if COS_BASE_URL else "/octopus-avatar.svg")
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY", default="")
DEEPSEEK_BASE_URL = env(
    "DEEPSEEK_BASE_URL",
    default=env("DEEPSEEK_API_BASE", default="https://api.deepseek.com/v1"),
)
DEEPSEEK_MODEL = env("DEEPSEEK_MODEL", default="deepseek-reasoner")

ARK_API_KEY = env("ARK_API_KEY", default=env("RK_API_KEY", default=""))
ARK_EMBEDDING_BASE_URL = env("ARK_EMBEDDING_BASE_URL", default="https://ark.cn-beijing.volces.com/api/v3")
ARK_EMBEDDING_MODEL = env("ARK_EMBEDDING_MODEL", default="doubao-embedding-vision-251215")
ARK_EMBEDDING_ENDPOINT = env("ARK_EMBEDDING_ENDPOINT", default="/embeddings/multimodal")
ARK_EMBEDDING_DIMENSIONS = env.int("ARK_EMBEDDING_DIMENSIONS", default=1024)
ARK_EMBEDDING_INSTRUCTIONS = env(
    "ARK_EMBEDDING_INSTRUCTIONS",
    default="Target_modality: text.\\nInstruction: summarize semantics for retrieval.\\nQuery:",
)
QDRANT_URL = env("QDRANT_URL", default="")
QDRANT_API_KEY = env("QDRANT_API_KEY", default="")
QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="oldboy_ai_customer")
AI_CS_LLM_BASE_URL = env("AI_CS_LLM_BASE_URL", default=DEEPSEEK_BASE_URL)
AI_CS_LLM_API_KEY = env("AI_CS_LLM_API_KEY", default=DEEPSEEK_API_KEY)
AI_CS_LLM_MODEL = env("AI_CS_LLM_MODEL", default=DEEPSEEK_MODEL)
AI_CS_TOP_K = env.int("AI_CS_TOP_K", default=5)
AI_CS_CONTEXT_MIN_SCORE = env.float("AI_CS_CONTEXT_MIN_SCORE", default=0.25)
AI_CS_ENABLE_RAG = env.bool("AI_CS_ENABLE_RAG", default=True)
AI_CS_KNOWLEDGE_MAX_UPLOAD_SIZE = env.int("AI_CS_KNOWLEDGE_MAX_UPLOAD_SIZE", default=100 * 1024 * 1024)
AI_CS_EMBED_BATCH_SIZE = env.int("AI_CS_EMBED_BATCH_SIZE", default=64)
SEARXNG_SEARCH_URL = env("SEARXNG_SEARCH_URL", default="")
SEARXNG_BASIC_USER = env("SEARXNG_BASIC_USER", default="")
SEARXNG_BASIC_PASS = env("SEARXNG_BASIC_PASS", default="")
ARK_EMBEDDING_TIMEOUT = env.int("ARK_EMBEDDING_TIMEOUT", default=8)
ARK_IMAGE_BASE_URL = env("ARK_IMAGE_BASE_URL", default="https://ark.cn-beijing.volces.com/api/v3")
ARK_IMAGE_MODEL = env("ARK_IMAGE_MODEL", default="doubao-seedream-4-5-251128")
ARK_IMAGE_FALLBACK_MODELS = env("ARK_IMAGE_FALLBACK_MODELS", default="doubao-seedream-5-0-260128")
ARK_IMAGE_SIZE = env("ARK_IMAGE_SIZE", default="2K")
ARK_IMAGE_OUTPUT_FORMAT = env("ARK_IMAGE_OUTPUT_FORMAT", default="png")
ARK_IMAGE_WATERMARK = env.bool("ARK_IMAGE_WATERMARK", default=False)
ARK_IMAGE_TIMEOUT = env.int("ARK_IMAGE_TIMEOUT", default=90)
AA1_HOT_URL = env("AA1_HOT_URL", default="https://v.api.aa1.cn/api/douyin-hot/index.php?aa1=hot")
HOTWORDS_CACHE_TTL = env.int("HOTWORDS_CACHE_TTL", default=1200)
AI_BLOGGER_HOTWORDS_MIN_INTERVAL = env.int("AI_BLOGGER_HOTWORDS_MIN_INTERVAL", default=10)
AI_BLOGGER_INPROCESS_QUEUE = env.bool("AI_BLOGGER_INPROCESS_QUEUE", default=True)
AI_BLOGGER_LLM_TIMEOUT = env.int("AI_BLOGGER_LLM_TIMEOUT", default=90)
AI_BLOGGER_IMAGE_TIMEOUT = env.int("AI_BLOGGER_IMAGE_TIMEOUT", default=90)
AI_BLOGGER_IMAGE_SIZE = env("AI_BLOGGER_IMAGE_SIZE", default="2K")
ARK_BASE_URL = env("ARK_BASE_URL", default="https://ark.cn-beijing.volces.com/api/v3")
SEEDREAM_MODEL = env("SEEDREAM_MODEL", default="doubao-seedream-4-5-251128")
SEEDANCE_MODEL = env("SEEDANCE_MODEL", default="doubao-seedance-1-5-pro-251215")
DEFAULT_VIDEO_DURATION = env.int("DEFAULT_VIDEO_DURATION", default=5)
DEFAULT_VIDEO_RATIO = env("DEFAULT_VIDEO_RATIO", default="adaptive")
DEFAULT_VIDEO_GENERATE_AUDIO = env.bool("DEFAULT_VIDEO_GENERATE_AUDIO", default=True)
DEFAULT_VIDEO_WATERMARK = env.bool("DEFAULT_VIDEO_WATERMARK", default=False)
AI_BLOGGER_VIDEO_CREATE_TIMEOUT = env.int("AI_BLOGGER_VIDEO_CREATE_TIMEOUT", default=60)
AI_BLOGGER_VIDEO_QUERY_TIMEOUT = env.int("AI_BLOGGER_VIDEO_QUERY_TIMEOUT", default=30)
AI_BLOGGER_VIDEO_POLL_INTERVAL = env.float("AI_BLOGGER_VIDEO_POLL_INTERVAL", default=3)
AI_BLOGGER_VIDEO_MAX_POLLS = env.int("AI_BLOGGER_VIDEO_MAX_POLLS", default=60)
AI_BLOGGER_POST_COST = env.float("AI_BLOGGER_POST_COST", default=20)
AI_BLOGGER_VIDEO_COST = env.float("AI_BLOGGER_VIDEO_COST", default=80)
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/1")
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=900)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=840)
CELERY_TASK_TRACK_STARTED = True
AI_BLOGGER_USE_CELERY = env.bool("AI_BLOGGER_USE_CELERY", default=True)

AI_RESUME_ASSISTANT_COST = env.int("AI_RESUME_ASSISTANT_COST", default=10)
AI_RESUME_OCR_URL = env("AI_RESUME_OCR_URL", default="")
AI_RESUME_OCR_PROVIDER = env("AI_RESUME_OCR_PROVIDER", default="json_base64")
AI_RESUME_OCR_TIMEOUT = env.int("AI_RESUME_OCR_TIMEOUT", default=45)
AI_RESUME_IMAGE_FETCH_TIMEOUT = env.int("AI_RESUME_IMAGE_FETCH_TIMEOUT", default=12)
AI_RESUME_LLM_TIMEOUT = env.int("AI_RESUME_LLM_TIMEOUT", default=120)
AI_RESUME_INPROCESS_QUEUE = env.bool("AI_RESUME_INPROCESS_QUEUE", default=True)
