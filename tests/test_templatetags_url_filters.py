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
Tests for application/templatetags/url_filters.py
"""

import pytest
from django.test import RequestFactory
from application.templatetags.url_filters import build_filter_url


def make_context(url="/enquiries/", params=None):
    """Helper: build a minimal template context with a GET request."""
    factory = RequestFactory()
    query = ""
    if params:
        from urllib.parse import urlencode

        query = urlencode(params)
    request = factory.get(url + ("?" + query if query else ""))
    return {"request": request}


class TestBuildFilterUrl:
    """Tests for the build_filter_url template tag."""

    def test_returns_question_mark_when_no_params(self):
        context = make_context()
        result = build_filter_url(context)
        assert result == "?"

    def test_adds_new_param_to_empty_querystring(self):
        context = make_context()
        result = build_filter_url(context, member=5)
        assert "member=5" in result
        assert result.startswith("?")

    def test_preserves_existing_params(self):
        context = make_context(params={"status": "open", "section": "3"})
        result = build_filter_url(context, member=7)
        assert "status=open" in result
        assert "section=3" in result
        assert "member=7" in result

    def test_replaces_existing_param_with_new_value(self):
        context = make_context(params={"member": "2"})
        result = build_filter_url(context, member=9)
        assert "member=9" in result
        # Old value should not appear
        assert "member=2" not in result

    def test_removes_param_when_value_is_empty_string(self):
        context = make_context(params={"member": "2", "status": "open"})
        result = build_filter_url(context, member="")
        assert "member" not in result
        assert "status=open" in result

    def test_removes_param_when_value_is_none(self):
        context = make_context(params={"member": "2", "status": "open"})
        result = build_filter_url(context, member=None)
        assert "member" not in result

    def test_removes_param_when_value_is_zero(self):
        """Zero is falsy so should be treated as empty and removed."""
        context = make_context(params={"member": "2"})
        result = build_filter_url(context, member=0)
        assert "member" not in result

    def test_returns_question_mark_when_all_params_empty(self):
        context = make_context(params={"member": ""})
        result = build_filter_url(context, status="")
        assert result == "?"
