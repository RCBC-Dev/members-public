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
Tests for application/context_processors.py
"""

import os
import pytest
from unittest.mock import patch
from django.test import RequestFactory
from application.context_processors import version_info


@pytest.fixture
def cp_request():
    return RequestFactory().get("/")


class TestVersionInfoContextProcessor:
    """Tests for the version_info context processor."""

    def test_returns_required_keys(self, cp_request):
        ctx = version_info(cp_request)
        assert "version" in ctx
        assert "change_log" in ctx
        assert "db_name" in ctx
        assert "db_server" in ctx
        assert "environment" in ctx
        assert "council_name" in ctx

    def test_environment_defaults_to_development(self, cp_request):
        env_backup = os.environ.pop("ENVIRONMENT", None)
        try:
            ctx = version_info(cp_request)
            assert ctx["environment"] == "DEVELOPMENT"
        finally:
            if env_backup is not None:
                os.environ["ENVIRONMENT"] = env_backup

    def test_environment_test_is_respected(self, cp_request):
        with patch.dict("os.environ", {"ENVIRONMENT": "TEST"}):
            ctx = version_info(cp_request)
            assert ctx["environment"] == "TEST"

    def test_environment_production_is_respected(self, cp_request):
        with patch.dict("os.environ", {"ENVIRONMENT": "PRODUCTION"}):
            ctx = version_info(cp_request)
            assert ctx["environment"] == "PRODUCTION"

    def test_environment_unknown_value_falls_back_to_development(self, cp_request):
        with patch.dict("os.environ", {"ENVIRONMENT": "STAGING"}):
            ctx = version_info(cp_request)
            assert ctx["environment"] == "DEVELOPMENT"

    def test_council_name_falls_back_to_default(self, cp_request):
        from django.conf import settings
        original = getattr(settings, "COUNCIL_NAME", None)
        try:
            if hasattr(settings, "COUNCIL_NAME"):
                delattr(settings, "COUNCIL_NAME")
            ctx = version_info(cp_request)
            assert ctx["council_name"] == "Your Council Name"
        finally:
            if original is not None:
                settings.COUNCIL_NAME = original

    def test_council_name_uses_settings_value(self, cp_request):
        from django.conf import settings
        with patch.object(settings, "COUNCIL_NAME", "Test Council", create=True):
            ctx = version_info(cp_request)
            assert ctx["council_name"] == "Test Council"

    def test_version_is_a_string(self, cp_request):
        ctx = version_info(cp_request)
        assert isinstance(ctx["version"], str)
