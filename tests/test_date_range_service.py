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
Tests for application/date_range_service.py
"""

import pytest
from datetime import date, timedelta
from django.test import RequestFactory
from application.date_range_service import DateRangeService


class TestDatesMatchPredefinedRange:
    """Tests for DateRangeService.dates_match_predefined_range."""

    def test_returns_false_for_empty_strings(self):
        assert DateRangeService.dates_match_predefined_range("", "") is False

    def test_returns_false_for_none_values(self):
        assert DateRangeService.dates_match_predefined_range(None, None) is False

    def test_returns_false_for_invalid_date_format(self):
        assert (
            DateRangeService.dates_match_predefined_range("not-a-date", "2024-01-01")
            is False
        )

    def test_matches_12months_preset(self):
        from application.date_utils import get_preset_date_range

        dr = get_preset_date_range("12months", timezone_aware=False)
        result = DateRangeService.dates_match_predefined_range(
            dr.date_from_str, dr.date_to_str
        )
        assert result is True

    def test_matches_3months_preset(self):
        from application.date_utils import get_preset_date_range

        dr = get_preset_date_range("3months", timezone_aware=False)
        result = DateRangeService.dates_match_predefined_range(
            dr.date_from_str, dr.date_to_str
        )
        assert result is True

    def test_does_not_match_arbitrary_dates(self):
        result = DateRangeService.dates_match_predefined_range(
            "2000-01-01", "2000-06-01"
        )
        assert result is False


class TestGetDefaultFilterParams:
    """Tests for DateRangeService.get_default_filter_params."""

    def test_returns_dict_with_status_and_date_range(self):
        result = DateRangeService.get_default_filter_params()
        assert "status" in result
        assert "date_range" in result

    def test_12months_includes_date_strings(self):
        result = DateRangeService.get_default_filter_params(date_range="12months")
        assert "date_from" in result
        assert "date_to" in result

    def test_all_range_does_not_include_date_strings(self):
        result = DateRangeService.get_default_filter_params(date_range="all")
        assert "date_from" not in result
        assert "date_to" not in result

    def test_status_is_passed_through(self):
        result = DateRangeService.get_default_filter_params(status="open")
        assert result["status"] == "open"


class TestGetDefaultFilterRedirect:
    """Tests for DateRangeService.get_default_filter_redirect."""

    def test_returns_http_response_redirect(self):
        from django.http import HttpResponseRedirect

        result = DateRangeService.get_default_filter_redirect("/enquiries/")
        assert isinstance(result, HttpResponseRedirect)

    def test_redirect_url_contains_path(self):
        result = DateRangeService.get_default_filter_redirect("/enquiries/")
        assert "/enquiries/" in result["Location"]


class TestCleanUrlParameters:
    """Tests for DateRangeService.clean_url_parameters."""

    def _make_querydict(self, params):
        from django.http import QueryDict

        qd = QueryDict(mutable=True)
        qd.update(params)
        return qd

    def test_removes_empty_values(self):
        qd = self._make_querydict({"status": "", "date_range": "12months"})
        clean, has_empty = DateRangeService.clean_url_parameters(qd)
        assert has_empty is True
        assert "status" not in clean or clean.get("status") == ""

    def test_preserves_non_empty_values(self):
        qd = self._make_querydict({"status": "open", "date_range": "6months"})
        clean, has_empty = DateRangeService.clean_url_parameters(qd)
        assert clean.get("status") == "open"

    def test_adds_default_date_range_when_missing(self):
        qd = self._make_querydict({})
        clean, has_empty = DateRangeService.clean_url_parameters(qd)
        assert clean.get("date_range") == "12months"
        assert has_empty is True


class TestGetFilterDates:
    """Tests for DateRangeService.get_filter_dates."""

    def test_all_returns_none_none(self):
        date_from, date_to = DateRangeService.get_filter_dates("all")
        assert date_from is None
        assert date_to is None

    def test_custom_returns_provided_dates(self):
        d1 = date(2024, 1, 1)
        d2 = date(2024, 6, 30)
        date_from, date_to = DateRangeService.get_filter_dates("custom", d1, d2)
        assert date_from == d1
        assert date_to == d2

    def test_12months_returns_date_objects(self):
        date_from, date_to = DateRangeService.get_filter_dates("12months")
        assert isinstance(date_from, date)
        assert isinstance(date_to, date)
        assert date_from < date_to

    def test_invalid_type_falls_back_to_12months(self):
        date_from, date_to = DateRangeService.get_filter_dates("quarterly")
        assert date_from is not None
        assert date_to is not None
