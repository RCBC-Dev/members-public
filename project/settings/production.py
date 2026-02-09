"""
Django production environment settings for Members Enquiries System.
"""

import os
from .base import *
from application.whitenoise_headers import add_cors_headers

# Get secret key from environment variable - no fallback to ensure proper configuration
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ["members2.redclev.net", "localhost"]

# Override base.py setting - MUST come after import
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# CSRF Trusted Origins - domains that are allowed to make POST requests
CSRF_TRUSTED_ORIGINS = ["https://members2.redclev.net"]

# CORS settings for test environment
# Only allow specific origins in test environment
CORS_ALLOWED_ORIGINS = ["https://members2.redclev.net"]
CORS_ALLOW_CREDENTIALS = True  # Allow credentials in test environment

# Static files configuration for production
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Add static files path to STATICFILES_DIRS
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Use a simpler storage backend for WhiteNoise
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Media files configuration
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": os.environ.get("DATABASE_NAME"),
        "USER": os.environ.get("DATABASE_USER"),
        "PASSWORD": os.environ.get(
            "DATABASE_PASSWORD"
        ),  # Required environment variable
        "HOST": os.environ.get("DATABASE_HOST"),
        "PORT": os.environ.get("DATABASE_PORT"),
        "OPTIONS": {
            "driver": "ODBC Driver 17 for SQL Server",
            "extra_params": "TrustServerCertificate=yes",
        },
    }
}

# Security Settings

# HSTS settings
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# SECURE_SSL_REDIRECT = True  # Disabled - IIS already handles HTTPS, causes redirect loop with Waitress

# Cookie security
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Strict"

# CORS settings
CORS_ALLOW_ALL_ORIGINS = False  # Explicitly set
CORS_ALLOWED_ORIGINS = [
    "https://members2.redclev.net",  # Only your domain
]
CORS_ALLOW_CREDENTIALS = True  # If you use cookies/session auth
WHITENOISE_ADD_HEADERS_FUNCTION = add_cors_headers
