"""
Shared test fixtures for the Members Enquiries application.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Configure Django settings for pytest-django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.development')

@pytest.fixture
def user(db):
    """Create a test user."""
    from django.contrib.auth.models import User
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='password123'
    )

@pytest.fixture
def admin_user(db):
    """Create a test admin user."""
    from django.contrib.auth.models import User
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )
