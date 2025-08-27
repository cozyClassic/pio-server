import os
from pathlib import Path

ENVIRON = os.environ.get("ENVIRON", "local")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_CLOUDFRONT_DOMAIN = os.environ.get("AWS_CLOUDFRONT_DOMAIN")
REVIEW_UPLOAD_KEY = os.environ.get("REVIEW_UPLOAD_KEY")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME")
AWS_CLOUDFRONT_KEY_ID = os.environ.get("AWS_CLOUDFRONT_KEY_ID")
AWS_CLOUDFRONT_KEY_PATH = os.environ.get("AWS_CLOUDFRONT_KEY_PATH")
if AWS_CLOUDFRONT_KEY_PATH:
    AWS_CLOUDFRONT_KEY = open(AWS_CLOUDFRONT_KEY_PATH).read()
else:
    AWS_CLOUDFRONT_KEY = open("cloudfront_private_key.pem").read()
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
SERVER_HOST = os.environ.get("SERVER_HOST", default="localhost:8000")
DB_NAME = os.environ.get("DB_NAME", default="postgres")
DB_USER = os.environ.get("DB_USER", default="postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", default="1234")
DB_HOST = os.environ.get("DB_HOST", default="localhost")
DB_PORT = os.environ.get("DB_PORT", default="5432")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = f"https://{AWS_CLOUDFRONT_DOMAIN}/static/"
if ENVIRON == "local":
    import environ

    STATIC_URL = "/static/"
    env = environ.Env(DEBUG=(bool, False))
    DEBUG = True
    environ.Env.read_env(os.path.join(BASE_DIR, ".local.env"))
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_CLOUDFRONT_DOMAIN = env("AWS_CLOUDFRONT_DOMAIN")
    REVIEW_UPLOAD_KEY = env("REVIEW_UPLOAD_KEY")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME")
    AWS_CLOUDFRONT_KEY_ID = env("AWS_CLOUDFRONT_KEY_ID")
    AWS_CLOUDFRONT_KEY = open("cloudfront_private_key.pem").read()
    SECRET_KEY = env("DJANGO_SECRET_KEY")
    SERVER_HOST = env("SERVER_HOST", default="localhost:8000")
    DB_NAME = env("DB_NAME", default="postgres")
    DB_USER = env("DB_USER", default="postgres")
    DB_PASSWORD = env("DB_PASSWORD", default="1234")
    DB_HOST = env("DB_HOST", default="localhost")
    DB_PORT = env("DB_PORT", default="5432")


else:
    CSRF_COOKIE_DOMAIN = None
    SESSION_COOKIE_DOMAIN = None

CORS_ALLOWED_ORIGINS = [
    "https://www.phoneinone.com",
    "https://phoneinone.com",
    "https://server.phoneinone.com",
    "https://settings.phoneinone.com",
    "https://test.phoneinone.com",
    "https://dev.phoneinone.com",
]

CORS_ALLOWED_METHODS = ["GET", "POST"]

# HTTP 환경에서도 작동하도록 설정
CSRF_TRUSTED_ORIGINS = [
    "https://server.phoneinone.com",
    "https://test.phoneinone.com",
    "https://phoneinone.com",
    "https://www.phoneinone.com",
    "https://dev.phoneinone.com",
    "http://" + SERVER_HOST + "",
]

ALLOWED_HOSTS = [
    "server.phoneinone.com",
    "test.phoneinone.com",
    "phoneinone.com",
    "dev.phoneinone.com",
    "*.myekmjwu.ap-northeast-2.elasticbeanstalk.com",
    "test-1.eba-myekmjwu.ap-northeast-2.elasticbeanstalk.com",
    SERVER_HOST.replace("http://", "").replace("https://", "").rstrip("/"),
]

# 3000~3004 이랑, db ID로 조회하는
if DEBUG:
    ALLOWED_HOSTS.append("localhost")
    ALLOWED_HOSTS.append("127.0.0.1")
    CSRF_TRUSTED_ORIGINS.append("http://localhost")
    CSRF_TRUSTED_ORIGINS.append("http://127.0.0.1")
    CSRF_TRUSTED_ORIGINS.append("http://localhost:3000")
    CSRF_TRUSTED_ORIGINS.append("http://localhost:3001")
    CSRF_TRUSTED_ORIGINS.append("http://localhost:3002")
    CSRF_TRUSTED_ORIGINS.append("http://localhost:3003")
    CSRF_TRUSTED_ORIGINS.append("http://localhost:3004")
    CORS_ALLOWED_ORIGINS.append("http://localhost:8000")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "ebhealthcheck.apps.EBHealthCheckConfig",
    "drf_yasg",
    "rest_framework",
    "phone",
    "nested_admin",
    "simple_history",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

APPEND_SLASH = False

ROOT_URLCONF = "phoneinone_server.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
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

WSGI_APPLICATION = "phoneinone_server.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Seoul"

USE_I18N = True

USE_TZ = True


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    "TRAILING_SLASH": False,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
}

if DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
            },
        },
        "loggers": {
            "django.db.backends": {
                "handlers": ["console"],
                "level": "DEBUG",
            },
        },
    }

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "cloudfront_key_id": AWS_CLOUDFRONT_KEY_ID,
            "cloudfront_key": AWS_CLOUDFRONT_KEY,
            "querystring_auth": False,
            "custom_domain": AWS_CLOUDFRONT_DOMAIN,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
