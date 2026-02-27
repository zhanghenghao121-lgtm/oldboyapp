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

# 线上有时会只配置 apex 域名，导致通过 www 访问时 API 返回 400 (DisallowedHost)。
# 这里补齐站点默认域名，避免登录页验证码、背景等接口加载失败。
DEFAULT_ALLOWED_HOSTS = ["oldboyai.com", "www.oldboyai.com", "localhost", "127.0.0.1"]
if "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, *DEFAULT_ALLOWED_HOSTS]))

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

MAX_UPLOAD_SIZE = env.int("MAX_UPLOAD_SIZE", default=50 * 1024 * 1024)
EMAIL_CODE_DAILY_LIMIT = env.int("EMAIL_CODE_DAILY_LIMIT", default=10)
