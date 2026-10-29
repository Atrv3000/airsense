"""
Django settings for AirSense Mumbai project.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project: BASE_DIR is 'backend/'
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from project root or backend directory
ROOT_DIR = BASE_DIR.parent
env_path = ROOT_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv(dotenv_path=BASE_DIR / '.env')

from django.core.exceptions import ImproperlyConfigured

# Detect if running in test environment (e.g. pytest / test command)
IS_TESTING = ('pytest' in sys.modules) or ('test' in sys.argv)

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# Secret Key Configuration
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG or IS_TESTING:
        SECRET_KEY = 'django-insecure-dev-fallback-key-only-for-local-debugging'
    else:
        raise ImproperlyConfigured(
            "CRITICAL SECURITY ERROR: SECRET_KEY environment variable is required in production."
        )

# Allowed Hosts Configuration (Strictly restricted to env values in production)
allowed_hosts_raw = os.getenv('ALLOWED_HOSTS')
if allowed_hosts_raw:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_raw.split(',') if host.strip()]
elif DEBUG or IS_TESTING:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '10.0.2.2', '[::1]', 'testserver', '*']
else:
    raise ImproperlyConfigured(
        "CRITICAL SECURITY ERROR: ALLOWED_HOSTS environment variable must be set in production."
    )

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party packages
    'rest_framework',
    'corsheaders',

    # AirSense Core Apps
    'core',
    'ingestion',
    'aqi_engine',
    'ml_engine',
    'spatial_gis',
    'alerts',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be at the very top for CORS headers
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'airsense_backend.urls'

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

WSGI_APPLICATION = 'airsense_backend.wsgi.application'

# Database Configuration (PostgreSQL 16/18)
DB_NAME = os.getenv('DB_NAME', 'airsense_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
if DB_PASSWORD is None:
    if DEBUG or IS_TESTING:
        DB_PASSWORD = 'postgres'
    else:
        raise ImproperlyConfigured(
            "CRITICAL SECURITY ERROR: DB_PASSWORD environment variable is required in production."
        )
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': DB_NAME,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static & Media Files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Settings with Rate Throttling
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('DRF_THROTTLE_ANON', '120/min'),
        'user': os.getenv('DRF_THROTTLE_USER', '600/min'),
    },
}

# Cross-Origin Resource Sharing (CORS) for Mobile & Web
cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS')
if cors_origins_env:
    CORS_ALLOWED_ORIGINS = [orig.strip() for orig in cors_origins_env.split(',') if orig.strip()]
    CORS_ALLOW_ALL_ORIGINS = False
elif DEBUG or IS_TESTING:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = []

CORS_ALLOW_CREDENTIALS = True

# Ingestion trigger secret key (always required for ingestion API endpoints)
INGESTION_SECRET_KEY = os.getenv('INGESTION_SECRET_KEY')
if not INGESTION_SECRET_KEY:
    if DEBUG or IS_TESTING:
        INGESTION_SECRET_KEY = 'dev-secret-ingestion-token-airsense'
    else:
        raise ImproperlyConfigured(
            "CRITICAL SECURITY ERROR: INGESTION_SECRET_KEY environment variable must be set in production."
        )

# ML Models Directory
ML_MODELS_DIR = BASE_DIR / 'ml_engine' / 'saved_models'
os.makedirs(ML_MODELS_DIR, exist_ok=True)

# Frame options: SAMEORIGIN allows embedded maps on same domain while protecting against clickjacking
X_FRAME_OPTIONS = 'SAMEORIGIN'
