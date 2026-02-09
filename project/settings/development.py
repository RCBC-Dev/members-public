"""
Django development settings for Members Enquiries project.
"""

from .base import *

# Import the original MIDDLEWARE from base to modify it
from .base import MIDDLEWARE as BASE_MIDDLEWARE

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# CSRF Trusted Origins - domains that are allowed to make POST requests
CSRF_TRUSTED_ORIGINS = ["http://localhost"]

# CORS settings for development
# In development, we allow requests from localhost
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
]
# For development only - do not use in production
CORS_ALLOW_CREDENTIALS = True

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# Override staticfiles storage for development to use Django's default
# This avoids potential conflicts with WhiteNoise in debug mode
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Modify MIDDLEWARE to remove WhiteNoise in development
# This allows Django's default static file serving to take precedence when DEBUG=True
MIDDLEWARE = [
    m for m in BASE_MIDDLEWARE if m != "whitenoise.middleware.WhiteNoiseMiddleware"
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Cache timeout settings (in seconds)
CACHE_TIMEOUTS = {
    "ENQUIRY_LIST": 300,  # 5 minutes for enquiry lists
    "CLOSED_ENQUIRY": 3600,  # 1 hour for closed enquiries (rarely change)
    "ENQUIRY_DETAIL": 300,  # 5 minutes for enquiry details
    "DASHBOARD_STATS": 600,  # 10 minutes for dashboard statistics
    "FILTER_OPTIONS": 1800,  # 30 minutes for dropdown options
}
