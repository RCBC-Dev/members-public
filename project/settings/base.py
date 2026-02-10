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
Django base settings for Members Enquiries System project.

These settings are common to all environments.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
from corsheaders.defaults import default_headers

load_dotenv()

DEBUG = False

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-t_*mwg#l@5#1*1^p_mueq6te^s0=h2^sa*$lbq!^&kc+6*1-&r"

# Session cookie age: 8 hours (28800 seconds)
SESSION_COOKIE_AGE = 28800
# What this means - if a user is inactive for 8 hours, they will need to login again (e.g., next workday)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    # Third-party apps
    "debug_toolbar",
    "crispy_forms",
    "crispy_bootstrap5",
    "tinymce",  # Django TinyMCE package for CSP-compliant rich text editing
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.microsoft",
    "corsheaders",
    # Local apps
    "application",
    "mssql",
]

# django-allauth requires a site id
SITE_ID = 1

# Site domain - should match your actual domain
# For development: 'localhost:8000'
# For production: 'yourdomain.com'
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "localhost:8000")

# Council email domain for determining email direction (incoming/outgoing)
COUNCIL_EMAIL_DOMAIN = "yourdomain.gov.uk"

MIDDLEWARE = [
    "project.middleware.csp.CSPMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # Add CORS middleware (must be before CommonMiddleware)
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Add WhiteNoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # Required for django-allauth
    "project.middleware.auth_security.MicrosoftAuthSanitizationMiddleware",  # Protect against XSL injection
    "project.middleware.auth_logging.AuthLoggingMiddleware",  # Log authentication attempts
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "application.context_processors.version_info",
            ],
        },
    },
]

# Authentication Backends (add allauth)
AUTHENTICATION_BACKENDS = [
    # Django default backend
    "django.contrib.auth.backends.ModelBackend",
    # allauth backend for Microsoft Entra ID
    "allauth.account.auth_backends.AuthenticationBackend",
]

WSGI_APPLICATION = "project.wsgi.application"

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-gb"

TIME_ZONE = "Europe/London"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# WhiteNoise configuration
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MAX_AGE = 31536000  # 1 year in seconds

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# File upload security settings
FILE_UPLOAD_MAX_MEMORY_SIZE = (
    5 * 1024 * 1024
)  # 5MB - files larger than this will be stored to disk
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB - total request size limit
FILE_UPLOAD_TEMP_DIR = None  # Use system default temp directory

# Custom file upload limits (used by our security service)
MAX_IMAGE_UPLOAD_SIZE = 15 * 1024 * 1024  # 15MB
MAX_EMAIL_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication settings
LOGIN_URL = "application:welcome"  # Microsoft SSO is now the primary login method
LOGIN_REDIRECT_URL = (
    "application:enquiry_list"  # Redirect to Enquiries list after successful login
)
ACCOUNT_SIGNUP_REDIRECT_URL = (
    "application:enquiry_list"  # Keep signup redirect consistent
)

# Admin login should use Django's built-in auth
ADMIN_LOGIN_URL = None  # Use Django's default admin login

# django-allauth settings
ACCOUNT_EMAIL_VERIFICATION = (
    "none"  # Can be set to 'mandatory' if email verification is required
)
ACCOUNT_LOGIN_METHODS = {
    "email",
    "username",
}  # Allow login with either username or email

# Skip intermediate confirmation page and go directly to provider
SOCIALACCOUNT_LOGIN_ON_GET = True
# Auto-signup for social accounts (creates account automatically if email matches)
SOCIALACCOUNT_AUTO_SIGNUP = True
# Disable signup since we're using existing accounts only
ACCOUNT_ADAPTER = "allauth.account.adapter.DefaultAccountAdapter"
# Use our custom secure adapter for social accounts
SOCIALACCOUNT_ADAPTER = "project.auth.adapters.SecureMicrosoftAdapter"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"  # Override with 'https' in production

# Preserve admin login functionality
ACCOUNT_LOGOUT_ON_GET = False  # Require POST for logout to maintain Django security
SOCIALACCOUNT_STORE_TOKENS = True

# Azure Entra ID settings from environment variables
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID")

# Microsoft Entra ID Configuration
# Using SOCIALACCOUNT_PROVIDERS approach as recommended by django-allauth documentation
SOCIALACCOUNT_PROVIDERS = {
    "microsoft": {
        "APPS": [
            {
                "client_id": AZURE_CLIENT_ID,
                "secret": AZURE_CLIENT_SECRET,
                "settings": {
                    "tenant": AZURE_TENANT_ID,
                },
            }
        ]
    }
}

# Debug Toolbar Settings
INTERNAL_IPS = [
    "127.0.0.1",
]


# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# TinyMCE Configuration - CSP-compliant rich text editor
TINYMCE_DEFAULT_CONFIG = {
    "height": 400,
    "width": "100%",
    "cleanup_on_startup": True,
    "custom_undo_redo_levels": 20,
    "selector": "textarea",
    "theme": "silver",
    "language": "en",  # Use 'en' instead of 'en_GB' to avoid 404
    "plugins": """
        save link codesample
        table code lists insertdatetime nonbreaking
        directionality searchreplace wordcount visualblocks
        visualchars autolink charmap anchor pagebreak
    """,
    "toolbar1": """
        bold italic underline | fontfamily fontsize |
        forecolor backcolor | alignleft alignright aligncenter alignjustify |
        indent outdent | bullist numlist table | link codesample
    """,
    "toolbar2": """
        visualblocks visualchars | charmap pagebreak nonbreaking anchor | code
    """,
    "menubar": "edit view insert format tools table help",
    "statusbar": True,
    "branding": False,  # Remove "Powered by TinyMCE" branding
    "promotion": False,  # Remove promotional elements
    "content_style": """
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
               font-size: 1rem; line-height: 1.5; margin: 1rem; }
        
        /* Dark mode support - applied via JavaScript */
        body.dark-mode-content { 
            background-color: #212529 !important; 
            color: #f8f9fa !important; 
        }
        body.light-mode-content { 
            background-color: #ffffff !important; 
            color: #212529 !important; 
        }
    """,
    "skin": "oxide",  # Default skin
    # 'setup': 'setupTinyMCEDarkMode',  # Temporarily disabled to fix JS error
    # Image embedding DISABLED - prevents search index pollution
    # Base64 images in description field would severely impact search performance
    # Use attachment system for images instead
    # Image embedding disabled to protect search performance
    "paste_data_images": False,  # Disable paste of images
}

# No database routers needed for Members Enquiries System

# CORS settings
# By default, CORS is disabled for security
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = []  # Empty list means no origins are allowed by default
CORS_ALLOW_CREDENTIALS = False  # Don't allow cookies in CORS requests by default

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/project.log",
            "formatter": "verbose",
        },
        "security_file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": "logs/security.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "project": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "project.security": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "application": {  # Logger for your specific app
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,  # Typically False for app-specific loggers
        },
    },
}

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers)  # import from corsheaders.defaults

# Members Enquiries Application Settings
ENQUIRY_OVERDUE_DAYS = 5  # Number of days after which an enquiry is considered overdue
ENQUIRY_SLA_DAYS = 5  # Service Level Agreement - days to respond to enquiries
ENQUIRY_DATE_RANGES = {
    "3months": 90,
    "6months": 183,
    "12months": 365,
}
