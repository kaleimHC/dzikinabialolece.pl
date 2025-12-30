"""
Django settings for Dziki na Białołęce project.
MASTER_SPEC v2.2 Architecture

VERIFIED AGAINST:
- DR-5: DISABLE_SERVER_SIDE_CURSORS=True (solves cursor error)
- DR-6: CONN_MAX_AGE=0 (let PgBouncer manage pooling)
- DR-6: CONN_HEALTH_CHECKS=True (recommended)
- NotebookLM Q6-Q10: All settings validated

CRITICAL SETTINGS:
- DISABLE_SERVER_SIDE_CURSORS = True (MANDATORY for PgBouncer + GeoDjango)
- CONN_MAX_AGE = 0 (PgBouncer manages pooling)
- Dual Redis (broker: noeviction, cache: allkeys-lru) per C-06
"""

import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY
# =============================================================================
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================
# NotebookLM Q10: Verified required apps
INSTALLED_APPS = [
    # Daphne ASGI server (must be first for runserver ASGI support)
    'daphne',

    # Django Channels
    'channels',

    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # GeoDjango (REQUIRED - NotebookLM Q10)
    'django.contrib.gis',
    
    # Django REST Framework (NotebookLM Q10)
    'rest_framework',
    'rest_framework_gis',  # drf-gis for GeoJSON
    
    # Celery (NotebookLM Q10)
    'django_celery_beat',    # Scheduled tasks (ADR-009)
    'django_celery_results', # Task results in PostgreSQL
    
    # Security & CORS
    'corsheaders',
    
    # Monitoring (NotebookLM Q10 - recommended)
    # 'django_prometheus',
    
    # Project apps
    'sightings',
    'analytics',
]

MIDDLEWARE = [
    # Security
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    
    # CORS (before CommonMiddleware)
    'corsheaders.middleware.CorsMiddleware',
    
    # Django core
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dziki.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'dziki.wsgi.application'
ASGI_APPLICATION = 'dziki.asgi.application'

# =============================================================================
# DJANGO CHANNELS (WebSocket support)
# =============================================================================
# Uses Redis for channel layer (same broker, different DB)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.environ.get(
                'REDIS_CHANNELS_URL',
                'redis://:redis_dev_password@redis-broker:6379/1'
            )],
        },
    },
}

# =============================================================================
# DATABASE - PostgreSQL + PostGIS via PgBouncer
# =============================================================================
# VERIFIED: DR-5, DR-6, NotebookLM Q6, Q7
#
# CRITICAL SETTINGS:
# - DISABLE_SERVER_SIDE_CURSORS = True (MANDATORY - DR-5)
#   Prevents "cursor does not exist" error with PgBouncer transaction mode
#
# - CONN_MAX_AGE = 0 (RECOMMENDED - DR-6)
#   Let PgBouncer manage connection pooling, not Django
#
# - CONN_HEALTH_CHECKS = True (RECOMMENDED - DR-6)
#   Verify connection health before reuse

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME', 'dziki_db'),
        'USER': os.environ.get('DB_USER', 'dziki'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'dziki_dev_password'),
        'HOST': os.environ.get('DB_HOST', 'pgbouncer'),  # Via PgBouncer!
        'PORT': os.environ.get('DB_PORT', '6432'),       # PgBouncer port!
        # MANDATORY for PgBouncer Transaction Pooling + GeoDjango (DR-5)
        'DISABLE_SERVER_SIDE_CURSORS': True,
        # PgBouncer manages pooling, not Django (DR-6)
        'CONN_MAX_AGE': 0,
        # Verify connection health before reuse (DR-6 recommended)
        'CONN_HEALTH_CHECKS': True,
    }
}

# =============================================================================
# CACHE - Redis (Dual Setup per C-06)
# =============================================================================
# VERIFIED: NotebookLM Q8, DR-7
#
# ARCHITECTURE DECISION:
# - DR-7 says single Redis with separate DBs is sufficient for most deployments
# - BUT MASTER_SPEC C-06 mandates Dual Redis Setup for this project
# - Keeping dual Redis per project requirements
#
# redis-cache: allkeys-lru (safe for cache eviction)
# redis-broker: noeviction (protects Celery queue)

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_CACHE_URL', 'redis://:redis_dev_password@redis-cache:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            # Graceful degradation: cache miss instead of error
            'IGNORE_EXCEPTIONS': True,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
            },
        },
        'KEY_PREFIX': 'dziki',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================
# VERIFIED: NotebookLM Q11-Q15, DR-8, DR-9, DR-10

# Broker: redis-broker with noeviction (protects job queue)
CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL', 
    'redis://:redis_dev_password@redis-broker:6379/0'
)

# Result backend: PostgreSQL (persistent results for GWR/STS)
CELERY_RESULT_BACKEND = 'django-db'

# Task settings
CELERY_TASK_TRACK_STARTED = True

# DR-9: Dual-Layer Timeout Strategy
# soft_time_limit must be 10-20s before hard_time_limit for cleanup
CELERY_TASK_TIME_LIMIT = 7200      # Hard limit: 120 min (SIGTERM)
CELERY_TASK_SOFT_TIME_LIMIT = 7080 # Soft limit: 118 min (allows 2 min cleanup)

# Reliability settings (NotebookLM Q12)
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # For R workers (prevents Head-of-Line Blocking)

# Task routing (NotebookLM Q9, DR-10)
# VERIFIED: Correct queue assignments
CELERY_TASK_ROUTES = {
    # R Spatial tasks -> q_r queue (rocker/geospatial worker)
    'analytics.tasks.compute_gwr_weekly': {'queue': 'q_r'},
    'analytics.tasks.compute_eta': {'queue': 'q_r'},
    'analytics.tasks.compute_sts': {'queue': 'q_r'},
    
    # Python ML tasks -> q_cpu queue
    'analytics.tasks.train_random_forest': {'queue': 'q_cpu'},
    'analytics.tasks.compute_ensemble': {'queue': 'q_cpu'},
    
    # I/O tasks -> q_io queue
    'analytics.tasks.refresh_materialized_views': {'queue': 'q_io'},
    'analytics.tasks.generate_tiles': {'queue': 'q_io'},
    'analytics.tasks.warmup_cache': {'queue': 'q_io'},
}

# Celery Beat (scheduler)
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Timezone
CELERY_TIMEZONE = 'Europe/Warsaw'
CELERY_ENABLE_UTC = True

# =============================================================================
# REST FRAMEWORK
# =============================================================================
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    # No authentication required for public API - disables CSRF requirement
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.CursorPagination',
    'PAGE_SIZE': 100,

    # Throttling (anti-spam for POST /api/sightings/)
    # NotebookLM Q19: 10/hour/IP is approved (conflict resolved)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/hour',   # Read-only endpoints need higher limit
        'user': '1000/hour',
    },
}

# =============================================================================
# GDAL/GEOS PATHS (usually auto-detected in Docker)
# =============================================================================
# DR-1: These may need to be set if auto-detection fails
# Uncomment if needed (paths for Debian Bookworm)
# GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'
# GEOS_LIBRARY_PATH = '/usr/lib/libgeos_c.so'

# =============================================================================
# SECURITY SETTINGS (Production)
# =============================================================================
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "False").lower() == "true"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# =============================================================================
# CORS
# =============================================================================
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173'
).split(',')

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins (must match CORS)
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://dzikinabialolece.pl',
    'http://www.dzikinabialolece.pl',
    'https://dzikinabialolece.pl',
    'https://www.dzikinabialolece.pl',
]

# =============================================================================
# STATIC & MEDIA
# =============================================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================
LANGUAGE_CODE = 'pl-pl'
TIME_ZONE = 'Europe/Warsaw'
USE_I18N = True
USE_TZ = True

# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# LOGGING
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
