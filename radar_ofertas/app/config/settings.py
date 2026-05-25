from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() == "true"


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
DEBUG = env_bool("DEBUG", False)
RENDER = env_bool("RENDER", False)
USE_SQLITE_FOR_RENDER = env_bool("USE_SQLITE_FOR_RENDER", False)
USE_EXTERNAL_STORAGE = env_bool("USE_EXTERNAL_STORAGE", False)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "s3")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "storages",
    "oportunidades",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if RENDER and USE_SQLITE_FOR_RENDER:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("SQLITE_PATH") or BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.getenv("DB_NAME", "radar_ofertas"),
            "USER": os.getenv("DB_USER", "sa"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "db"),
            "PORT": os.getenv("DB_PORT", "1433"),
            "OPTIONS": {
                "driver": "ODBC Driver 18 for SQL Server",
                "extra_params": "TrustServerCertificate=yes",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / "media"

if USE_EXTERNAL_STORAGE:
    if STORAGE_BACKEND != "s3":
        raise ValueError("STORAGE_BACKEND no soportado. Por ahora usar STORAGE_BACKEND=s3.")

    AWS_STORAGE_BUCKET_NAME = os.getenv("STORAGE_BUCKET_NAME", "")
    AWS_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY", "")
    AWS_S3_REGION_NAME = os.getenv("STORAGE_REGION_NAME", "")
    AWS_S3_ENDPOINT_URL = os.getenv("STORAGE_ENDPOINT_URL") or None
    AWS_S3_CUSTOM_DOMAIN = os.getenv("STORAGE_CUSTOM_DOMAIN") or None
    AWS_DEFAULT_ACL = os.getenv("STORAGE_DEFAULT_ACL", "private")
    AWS_QUERYSTRING_AUTH = AWS_DEFAULT_ACL == "private"
    AWS_S3_FILE_OVERWRITE = False
    AWS_LOCATION = "media"

    storage_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "access_key": AWS_ACCESS_KEY_ID,
        "secret_key": AWS_SECRET_ACCESS_KEY,
        "region_name": AWS_S3_REGION_NAME or None,
        "endpoint_url": AWS_S3_ENDPOINT_URL,
        "default_acl": AWS_DEFAULT_ACL,
        "querystring_auth": AWS_QUERYSTRING_AUTH,
        "file_overwrite": AWS_S3_FILE_OVERWRITE,
        "location": AWS_LOCATION,
    }
    if AWS_S3_CUSTOM_DOMAIN:
        storage_options["custom_domain"] = AWS_S3_CUSTOM_DOMAIN
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": storage_options,
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if RENDER:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}
