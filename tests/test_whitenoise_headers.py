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
Tests for application/whitenoise_headers.py
"""

import os
import pytest
from unittest.mock import patch
from application.whitenoise_headers import add_cors_headers


class TestAddCorsHeaders:
    """Tests for add_cors_headers function."""

    def test_adds_access_control_allow_origin(self):
        headers = {}
        with patch.dict(os.environ, {"DOMAIN": "example.com", "ENVIRONMENT": ""}):
            add_cors_headers(headers)
        assert "Access-Control-Allow-Origin" in headers

    def test_adds_vary_origin_header(self):
        headers = {}
        with patch.dict(os.environ, {"DOMAIN": "example.com", "ENVIRONMENT": ""}):
            add_cors_headers(headers)
        assert headers["Vary"] == "Origin"

    def test_development_uses_http(self):
        headers = {}
        with patch.dict(os.environ, {"DOMAIN": "example.com", "ENVIRONMENT": "development"}):
            add_cors_headers(headers)
        assert headers["Access-Control-Allow-Origin"].startswith("http://")

    def test_production_uses_https(self):
        headers = {}
        with patch.dict(os.environ, {"DOMAIN": "example.com", "ENVIRONMENT": "production"}):
            add_cors_headers(headers)
        assert headers["Access-Control-Allow-Origin"].startswith("https://")

    def test_test_environment_uses_https(self):
        headers = {}
        with patch.dict(os.environ, {"DOMAIN": "mysite.com", "ENVIRONMENT": "test"}):
            add_cors_headers(headers)
        assert headers["Access-Control-Allow-Origin"].startswith("https://")

    def test_empty_environment_uses_http(self):
        headers = {}
        with patch.dict(os.environ, {"DOMAIN": "localhost", "ENVIRONMENT": ""}):
            add_cors_headers(headers)
        assert headers["Access-Control-Allow-Origin"].startswith("http://")

    def test_domain_included_in_origin(self):
        headers = {}
        with patch.dict(os.environ, {"DOMAIN": "mycouncil.gov.uk", "ENVIRONMENT": "production"}):
            add_cors_headers(headers)
        assert "mycouncil.gov.uk" in headers["Access-Control-Allow-Origin"]

    def test_default_domain_is_localhost(self):
        headers = {}
        # Remove DOMAIN from env to test default
        env = {k: v for k, v in os.environ.items() if k != "DOMAIN"}
        env["ENVIRONMENT"] = ""
        with patch.dict(os.environ, env, clear=True):
            add_cors_headers(headers)
        assert "localhost" in headers["Access-Control-Allow-Origin"]
