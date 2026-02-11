# Copyright (C) 2026 Redcar & Cleveland Borough Council
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Django test environment settings for Members Enquiries project.
"""

import os
from .base import *
from application.whitenoise_headers import add_cors_headers

# Get secret key from environment variable - no fallback to ensure proper configuration
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [DOMAIN, "localhost"]

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# CSRF Trusted Origins - domains that are allowed to make POST requests
CSRF_TRUSTED_ORIGINS = [f"https://{DOMAIN}"]

# CORS settings for test environment
# Only allow specific origins in test environment
CORS_ALLOWED_ORIGINS = [f"https://{DOMAIN}"]
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
            "driver": "ODBC Driver 17 for SQL Server",  # This might need to be changed to 18 depending on the MS SQL Driver you download
            "extra_params": "TrustServerCertificate=yes",
        },
    }
}

# Security Settings

# HSTS settings
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie security
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Strict"

# CORS settings (CORS_ALLOWED_ORIGINS already defined above)
CORS_ALLOW_ALL_ORIGINS = False  # Explicitly set
CORS_ALLOW_CREDENTIALS = True  # Allow credentials in CORS requests
WHITENOISE_ADD_HEADERS_FUNCTION = add_cors_headers
