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
Tests for application/templatetags/list_extras.py
"""

import pytest
from datetime import date, datetime
from django.utils import timezone
from application.templatetags.list_extras import (
    list_index,
    days_between,
    business_days_between,
    working_days_between,
    resolution_time_color,
    working_days_due_date,
    resolution_time_display,
)


class TestListIndex:
    """Tests for list_index filter."""

    def test_returns_item_at_valid_index(self):
        assert list_index(["a", "b", "c"], 0) == "a"

    def test_returns_empty_string_for_out_of_range(self):
        assert list_index([1, 2], 99) == ""

    def test_returns_empty_string_for_non_numeric_arg(self):
        assert list_index([1, 2], "oops") == ""

    def test_returns_empty_string_for_none_arg(self):
        assert list_index([1, 2], None) == ""


class TestDaysBetween:
    """Tests for the days_between filter."""

    def test_returns_calendar_days(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 8)
        result = days_between(start, end)
        assert result == 7

    def test_same_date_returns_zero(self):
        d = date(2024, 6, 1)
        assert days_between(d, d) == 0


class TestBusinessDaysBetween:
    """Tests for the business_days_between filter."""

    def test_monday_to_friday_is_four_days(self):
        start = date(2024, 1, 1)   # Monday
        end = date(2024, 1, 5)     # Friday
        result = business_days_between(start, end)
        assert result == 4

    def test_same_date_returns_zero(self):
        d = date(2024, 1, 1)
        assert business_days_between(d, d) == 0


class TestWorkingDaysBetween:
    """Tests for the working_days_between filter (same as business days currently)."""

    def test_returns_same_as_business_days(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 5)
        assert working_days_between(start, end) == business_days_between(start, end)


class TestResolutionTimeColor:
    """Tests for the resolution_time_color filter."""

    def test_returns_empty_string_for_none(self):
        assert resolution_time_color(None) == ""

    def test_returns_success_for_one_day(self):
        assert resolution_time_color(1) == "text-success"

    def test_returns_success_for_zero_days(self):
        assert resolution_time_color(0) == "text-success"

    def test_returns_warning_for_five_days(self):
        assert resolution_time_color(5) == "text-warning"

    def test_returns_warning_for_two_days(self):
        assert resolution_time_color(2) == "text-warning"

    def test_returns_danger_for_six_days(self):
        assert resolution_time_color(6) == "text-danger"

    def test_returns_danger_for_large_number(self):
        assert resolution_time_color(100) == "text-danger"

    def test_returns_empty_string_for_non_numeric(self):
        assert resolution_time_color("bad") == ""

    def test_works_with_string_number(self):
        assert resolution_time_color("3") == "text-warning"


class TestWorkingDaysDueDate:
    """Tests for the working_days_due_date filter."""

    def test_returns_a_date(self):
        created = timezone.now()
        result = working_days_due_date(created, 5)
        assert result is not None

    def test_due_date_is_after_created_date(self):
        created = timezone.now()
        result = working_days_due_date(created, 5)
        assert result >= created.date()


class TestResolutionTimeDisplay:
    """Tests for the resolution_time_display inclusion tag."""

    def _make_enquiry(self, status, created_at=None, closed_at=None):
        """Build a simple mock enquiry object."""
        from unittest.mock import MagicMock
        enquiry = MagicMock()
        enquiry.status = status
        enquiry.created_at = created_at or timezone.now() - timezone.timedelta(days=3)
        enquiry.closed_at = closed_at
        return enquiry

    def test_returns_show_time_false_for_open_enquiry(self):
        enquiry = self._make_enquiry("open")
        result = resolution_time_display(enquiry)
        assert result == {"show_time": False}

    def test_returns_show_time_false_when_no_closed_at(self):
        enquiry = self._make_enquiry("closed", closed_at=None)
        result = resolution_time_display(enquiry)
        assert result == {"show_time": False}

    def test_returns_show_time_true_for_closed_enquiry(self):
        created = timezone.now() - timezone.timedelta(days=3)
        closed = timezone.now()
        enquiry = self._make_enquiry("closed", created_at=created, closed_at=closed)
        result = resolution_time_display(enquiry)
        assert result["show_time"] is True
        assert "business_days" in result
        assert "calendar_days" in result
        assert "color_class" in result
