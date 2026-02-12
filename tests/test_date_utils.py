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
Tests for application/date_utils.py
"""

import pytest
from datetime import date, datetime, timedelta
from django.utils import timezone
from application.date_utils import (
    DateRange,
    DateRangeCalculator,
    get_date_range_calculator,
    parse_request_date_range,
    get_preset_date_range,
    get_javascript_date_constants,
    get_date_range_description,
    get_date_range_subtitle,
    get_page_title_with_date_range,
    build_enquiry_list_url,
)


class TestDateRangeCalculator:
    """Tests for DateRangeCalculator."""

    def test_calculates_12months_range(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_preset_range("12months")
        assert dr.range_type == "12months"
        assert dr.months == 12
        assert dr.date_from is not None
        assert dr.date_to is not None

    def test_calculates_6months_range(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_preset_range("6months")
        assert dr.months == 6

    def test_calculates_3months_range(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_preset_range("3months")
        assert dr.months == 3

    def test_all_range_returns_none_dates(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_preset_range("all")
        assert dr.date_from is None
        assert dr.date_to is None
        assert dr.range_type == "all"

    def test_unknown_range_defaults_to_12months(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_preset_range("bogus")
        assert dr.months == 12

    def test_date_from_is_before_date_to(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_preset_range("3months")
        assert dr.date_from < dr.date_to

    def test_timezone_aware_returns_aware_datetimes(self):
        calc = DateRangeCalculator(timezone_aware=True)
        dr = calc.calculate_preset_range("12months")
        assert timezone.is_aware(dr.date_from)
        assert timezone.is_aware(dr.date_to)

    def test_date_strings_in_iso_format(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_preset_range("12months")
        # Should parse without error
        datetime.strptime(dr.date_from_str, "%Y-%m-%d")
        datetime.strptime(dr.date_to_str, "%Y-%m-%d")


class TestDateRangeCalculatorCustomRange:
    """Tests for DateRangeCalculator.calculate_custom_range."""

    def test_parses_valid_date_strings(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_custom_range("2024-01-01", "2024-03-31")
        assert dr.range_type == "custom"
        assert dr.date_from_str == "2024-01-01"
        assert dr.date_to_str == "2024-03-31"

    def test_invalid_date_from_results_in_none(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_custom_range("not-a-date", "2024-03-31")
        assert dr.date_from is None

    def test_invalid_date_to_results_in_none(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_custom_range("2024-01-01", "bad-date")
        assert dr.date_to is None

    def test_none_dates_give_empty_strings(self):
        calc = DateRangeCalculator(timezone_aware=False)
        dr = calc.calculate_custom_range(None, None)
        assert dr.date_from_str == ""
        assert dr.date_to_str == ""
        assert dr.date_from is None


class TestDateRangeCalculatorParseRequest:
    """Tests for DateRangeCalculator.parse_request_dates."""

    def _make_request(self, params):
        from django.test import RequestFactory
        return RequestFactory().get("/", params)

    def test_parses_preset_range_from_request(self):
        calc = DateRangeCalculator(timezone_aware=False)
        req = self._make_request({"date_range": "6months"})
        dr = calc.parse_request_dates(req)
        assert dr.range_type == "6months"

    def test_parses_custom_range_from_request(self):
        calc = DateRangeCalculator(timezone_aware=False)
        req = self._make_request(
            {"date_range": "custom", "date_from": "2024-01-01", "date_to": "2024-06-30"}
        )
        dr = calc.parse_request_dates(req)
        assert dr.range_type == "custom"

    def test_defaults_to_12months_when_no_params(self):
        calc = DateRangeCalculator(timezone_aware=False)
        req = self._make_request({})
        dr = calc.parse_request_dates(req)
        assert dr.range_type == "12months"

    def test_custom_dates_that_differ_from_preset_become_custom(self):
        calc = DateRangeCalculator(timezone_aware=False)
        req = self._make_request(
            {"date_range": "3months", "date_from": "2020-01-01", "date_to": "2020-12-31"}
        )
        dr = calc.parse_request_dates(req)
        assert dr.range_type == "custom"


class TestDateRangeCalculatorJavaScriptDates:
    """Tests for DateRangeCalculator.get_javascript_dates."""

    def test_returns_all_three_ranges(self):
        calc = DateRangeCalculator(timezone_aware=False)
        js_dates = calc.get_javascript_dates()
        assert "3months" in js_dates
        assert "6months" in js_dates
        assert "12months" in js_dates
        assert "today" in js_dates

    def test_today_is_iso_formatted(self):
        calc = DateRangeCalculator(timezone_aware=False)
        js_dates = calc.get_javascript_dates()
        datetime.strptime(js_dates["today"], "%Y-%m-%d")


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_date_range_calculator_returns_calculator(self):
        calc = get_date_range_calculator()
        assert isinstance(calc, DateRangeCalculator)

    def test_get_preset_date_range_returns_date_range(self):
        dr = get_preset_date_range("12months")
        assert isinstance(dr, DateRange)

    def test_get_javascript_date_constants_returns_dict(self):
        result = get_javascript_date_constants()
        assert isinstance(result, dict)
        assert "today" in result


class TestGetDateRangeDescription:
    """Tests for get_date_range_description."""

    def _make_dr(self, range_type, months=None, from_str="", to_str=""):
        return DateRange(
            date_from=None, date_to=None,
            date_from_str=from_str, date_to_str=to_str,
            range_type=range_type, months=months
        )

    def test_all_range_description(self):
        dr = self._make_dr("all")
        assert "all time" in get_date_range_description(dr)

    def test_custom_range_description(self):
        dr = self._make_dr("custom")
        assert "custom" in get_date_range_description(dr)

    def test_12months_description(self):
        dr = self._make_dr("12months", months=12)
        assert "12" in get_date_range_description(dr)

    def test_unknown_range_description(self):
        dr = self._make_dr("quarterly")
        result = get_date_range_description(dr)
        assert "selected period" in result

    def test_include_dates_appends_formatted_dates(self):
        dr = self._make_dr("12months", months=12, from_str="2024-01-01", to_str="2024-12-31")
        result = get_date_range_description(dr, include_dates=True)
        assert "01/01/2024" in result
        assert "31/12/2024" in result

    def test_custom_prefix(self):
        dr = self._make_dr("all")
        result = get_date_range_description(dr, prefix="during")
        assert result.startswith("during")


class TestGetDateRangeSubtitle:
    """Tests for get_date_range_subtitle."""

    def test_returns_showing_data_prefix(self):
        dr = DateRange(None, None, "", "", "12months", 12)
        result = get_date_range_subtitle(dr)
        assert result.startswith("Showing data")


class TestGetPageTitleWithDateRange:
    """Tests for get_page_title_with_date_range."""

    def _make_dr(self, range_type, months=None, from_str="", to_str=""):
        return DateRange(None, None, from_str, to_str, range_type, months)

    def test_all_time_title(self):
        dr = self._make_dr("all")
        result = get_page_title_with_date_range("Workload", dr)
        assert "All Time" in result

    def test_preset_months_title(self):
        dr = self._make_dr("6months", months=6)
        result = get_page_title_with_date_range("Workload", dr)
        assert "Last 6 Months" in result

    def test_custom_range_title_with_dates(self):
        dr = self._make_dr("custom", from_str="2024-01-01", to_str="2024-12-31")
        result = get_page_title_with_date_range("Workload", dr)
        assert "01/01/2024" in result

    def test_custom_range_title_without_dates(self):
        dr = self._make_dr("custom")
        result = get_page_title_with_date_range("Workload", dr)
        assert "Custom Range" in result

    def test_unknown_range_title(self):
        dr = self._make_dr("quarterly")
        result = get_page_title_with_date_range("Workload", dr)
        assert "Selected Period" in result

    def test_base_title_included(self):
        dr = self._make_dr("all")
        result = get_page_title_with_date_range("My Report", dr)
        assert "My Report" in result


class TestBuildEnquiryListUrl:
    """Tests for build_enquiry_list_url."""

    def _make_dr(self, range_type, from_str="", to_str=""):
        return DateRange(None, None, from_str, to_str, range_type, None)

    def test_includes_date_range_param(self):
        dr = self._make_dr("12months")
        result = build_enquiry_list_url({}, dr)
        assert "date_range=12months" in result

    def test_includes_base_params(self):
        dr = self._make_dr("all")
        result = build_enquiry_list_url({"status": "closed"}, dr)
        assert "status=closed" in result

    def test_custom_range_includes_dates(self):
        dr = self._make_dr("custom", from_str="2024-01-01", to_str="2024-06-30")
        result = build_enquiry_list_url({}, dr)
        assert "date_from=2024-01-01" in result
        assert "date_to=2024-06-30" in result

    def test_preset_range_does_not_include_specific_dates(self):
        dr = self._make_dr("6months")
        result = build_enquiry_list_url({}, dr)
        assert "date_from" not in result
        assert "date_to" not in result

    def test_result_starts_with_question_mark(self):
        dr = self._make_dr("all")
        result = build_enquiry_list_url({}, dr)
        assert result.startswith("?")


class TestDateUtilsErrorBranches:
    """Tests for error-handling branches in date_utils.py."""

    def _make_dr(self, range_type, months=None, from_str="", to_str=""):
        return DateRange(None, None, from_str, to_str, range_type, months)

    def test_invalid_date_string_in_description_does_not_raise(self):
        dr = self._make_dr("custom", from_str="not-a-date", to_str="also-not-a-date")
        # include_dates=True will try to parse and hit ValueError
        result = get_date_range_description(dr, include_dates=True)
        # Should not raise; the ValueError is caught silently
        assert isinstance(result, str)

    def test_invalid_date_string_in_subtitle_falls_back(self):
        dr = self._make_dr("custom", from_str="not-a-date", to_str="also-not-a-date")
        result = get_date_range_subtitle(dr)
        # Should return fallback string without crashing
        assert isinstance(result, str)
        assert len(result) > 0

    def test_invalid_date_string_in_page_title_falls_back(self):
        dr = self._make_dr("custom", from_str="not-a-date", to_str="also-not-a-date")
        result = get_page_title_with_date_range("Report", dr)
        assert isinstance(result, str)
        assert "Custom Range" in result

    def test_parse_request_dates_invalid_date_from_string(self):
        """Invalid date_from string in request is handled without error."""
        from unittest.mock import MagicMock
        calc = DateRangeCalculator(timezone_aware=True)
        mock_request = MagicMock()
        mock_request.GET = {"date_range": "custom", "date_from": "invalid", "date_to": "2024-06-30"}
        result = calc.parse_request_dates(mock_request, "12months")
        # Should not raise
        assert result is not None

    def test_parse_request_dates_invalid_date_to_string(self):
        """Invalid date_to string in request is handled without error."""
        from unittest.mock import MagicMock
        calc = DateRangeCalculator(timezone_aware=True)
        mock_request = MagicMock()
        mock_request.GET = {"date_range": "custom", "date_from": "2024-01-01", "date_to": "invalid"}
        result = calc.parse_request_dates(mock_request, "12months")
        assert result is not None
