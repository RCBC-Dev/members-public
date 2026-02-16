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
Tests for project/views.py
"""

import os
import tempfile
import pytest
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestServeMediaFile:
    """Tests for the serve_media_file view."""

    def _login(self, client):
        user = User.objects.create_user(username="mediauser", password="pass123")
        client.login(username="mediauser", password="pass123")
        return user

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/media/test.txt")
        assert response.status_code in (301, 302)

    def test_missing_file_returns_404(self, client, settings):
        self._login(client)
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            response = client.get("/media/nonexistent_file_xyz.txt")
            assert response.status_code == 404

    def test_existing_file_is_served(self, client, settings):
        self._login(client)
        # ignore_cleanup_errors=True avoids Windows file-lock errors when
        # Django's serve() still holds the file handle during teardown
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            test_file = os.path.join(tmpdir, "testfile.txt")
            with open(test_file, "w") as f:
                f.write("hello")
            response = client.get("/media/testfile.txt")
            assert response.status_code == 200
