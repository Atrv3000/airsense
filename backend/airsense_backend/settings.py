"""
Django settings for AirSense Mumbai project.
"""

import os
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

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-airsense-mumbai-aqi-fallback-key')
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

if DEBUG:
    allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,10.0.2.2,*')
else:
    allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,10.0.2.2')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_raw.split(',') if host.strip()]

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
DB_PASSWORD = os.getenv('DB_PASSWORD', 'abcd1234')
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

# Django REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Cross-Origin Resource Sharing (CORS) for Mobile & Web
CORS_ALLOW_ALL_ORIGINS = True  # Required for mobile simulator/LAN Expo app access
CORS_ALLOW_CREDENTIALS = True

# Ingestion trigger secret key (optional protection token)
INGESTION_SECRET_KEY = os.getenv('INGESTION_SECRET_KEY', '')

# ML Models Directory
ML_MODELS_DIR = BASE_DIR / 'ml_engine' / 'saved_models'
os.makedirs(ML_MODELS_DIR, exist_ok=True)

# Frame options: SAMEORIGIN allows embedded maps on same domain while protecting against clickjacking
X_FRAME_OPTIONS = 'SAMEORIGIN'
