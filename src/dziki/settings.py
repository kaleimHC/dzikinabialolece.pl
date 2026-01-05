"""
Django settings for Dziki na Białołęce.
"""

import logging
import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Fail fast in production if developer credentials are still in use.
# A misconfigured deploy (missing .env) would silently use the dev key,
# making session cookies forgeable and CSRF protection void.
if not DEBUG and "dev-secret-key-change-in-production" in SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "SECRET_KEY is set to the development default. "
        "Set SECRET_KEY environment variable before running in production."
    )

# APPLICATION DEFINITION
INSTALLED_APPS = [
    "daphne",  # ASGI server (must be first)
    "channels",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_gis",
    "django_celery_beat",
    "django_celery_results",
    "corsheaders",
    "sightings",
    "analytics",
]

MIDDLEWARE = [
    # Security
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # CORS (before CommonMiddleware)
    "corsheaders.middleware.CorsMiddleware",
    # Django core
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dziki.urls"

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

WSGI_APPLICATION = "dziki.wsgi.application"
ASGI_APPLICATION = "dziki.asgi.application"

# DJANGO CHANNELS (WebSocket support)
# Uses Redis for channel layer (same broker, different DB)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                os.environ.get(
                    "REDIS_CHANNELS_URL",
                    "redis://:redis_dev_password@redis-broker:6379/1",
                )
            ],
        },
    },
}

# DATABASE — PostgreSQL + PostGIS via PgBouncer
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("DB_NAME", "dziki_db"),
        "USER": os.environ.get("DB_USER", "dziki"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "dziki_dev_password"),
        "HOST": os.environ.get("DB_HOST", "pgbouncer"),
        "PORT": os.environ.get("DB_PORT", "6432"),
        # Mandatory for PgBouncer transaction pooling: prevents "cursor does not exist"
        "DISABLE_SERVER_SIDE_CURSORS": True,
        # Let PgBouncer manage connection pooling, not Django
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
    }
}

# CACHE — Redis (dual setup: broker=noeviction, cache=allkeys-lru)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get(
            "REDIS_CACHE_URL", "redis://:redis_dev_password@redis-cache:6379/0"
        ),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Graceful degradation: cache miss instead of error
            "IGNORE_EXCEPTIONS": True,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
            },
        },
        "KEY_PREFIX": "dziki",
        "TIMEOUT": 300,  # 5 minutes default
    }
}

# CELERY CONFIGURATION
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL", "redis://:redis_dev_password@redis-broker:6379/0"
)
CELERY_RESULT_BACKEND = "django-db"
CELERY_TASK_TRACK_STARTED = True
# soft_time_limit must be 10-20s before hard_time_limit to allow cleanup
CELERY_TASK_TIME_LIMIT = 7200
CELERY_TASK_SOFT_TIME_LIMIT = 7080
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Prevents head-of-line blocking for R workers
CELERY_TASK_ROUTES = {
    "analytics.tasks.refresh_materialized_views": {"queue": "q_io"},
    "analytics.tasks.warmup_cache": {"queue": "q_io"},
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = "Europe/Warsaw"
CELERY_ENABLE_UTC = True

# REST FRAMEWORK
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1000/hour",
        "user": "1000/hour",
        "pipeline_run": "60/hour",
        "samples_switch": "40/hour",
    },
}

# GDAL/GEOS usually auto-detected in Docker; uncomment if detection fails:
# GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'
# GEOS_LIBRARY_PATH = '/usr/lib/libgeos_c.so'

# SECURITY SETTINGS (Production)
_settings_logger = logging.getLogger(__name__)

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = (
        os.environ.get("SECURE_SSL_REDIRECT", "False").lower() == "true"
    )
    if not SECURE_SSL_REDIRECT:
        _settings_logger.warning(
            "SECURE_SSL_REDIRECT=False in production — set SECURE_SSL_REDIRECT=True or ensure "
            "SSL termination happens upstream (e.g. nginx/load balancer handles HTTPS)."
        )
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
).split(",")

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins (must match CORS)
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://dzikinabialolece.pl",
    "http://www.dzikinabialolece.pl",
    "https://dzikinabialolece.pl",
    "https://www.dzikinabialolece.pl",
]

# STATIC & MEDIA
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# INTERNATIONALIZATION
LANGUAGE_CODE = "pl-pl"
TIME_ZONE = "Europe/Warsaw"
USE_I18N = True
USE_TZ = True

# DEFAULT PRIMARY KEY
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# LOGGING
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
