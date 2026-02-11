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
Shared test fixtures for the Members Enquiries application.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Configure Django settings for pytest-django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings.development")


@pytest.fixture
def user(db):
    """Create a test user."""
    from django.contrib.auth.models import User

    return User.objects.create_user(
        username="testuser", email="test@example.com", password="password123"
    )


@pytest.fixture
def admin_user(db):
    """Create a test admin user."""
    from django.contrib.auth.models import User

    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="adminpass123"
    )
