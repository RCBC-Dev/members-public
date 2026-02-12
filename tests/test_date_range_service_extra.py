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
Additional tests for uncovered methods in application/date_range_service.py
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from application.date_range_service import DateRangeService


def _make_form(valid=True, date_range="12months", date_from=None, date_to=None):
    """Create a mock filter form."""
    form = MagicMock()
    form.is_valid.return_value = valid
    form.cleaned_data = {
        "date_range": date_range,
        "date_from": date_from,
        "date_to": date_to,
    }
    return form


def _make_queryset():
    """Create a mock queryset that supports chaining."""
    qs = MagicMock()
    qs.filter.return_value = qs
    return qs


class TestApplyDateFilters:
    """Tests for DateRangeService.apply_date_filters."""

    def test_invalid_form_returns_queryset_unchanged(self):
        qs = _make_queryset()
        form = _make_form(valid=False)
        result = DateRangeService.apply_date_filters(qs, form)
        qs.filter.assert_not_called()

    def test_all_date_range_no_filtering(self):
        qs = _make_queryset()
        form = _make_form(date_range="all")
        result = DateRangeService.apply_date_filters(qs, form)
        qs.filter.assert_not_called()

    def test_custom_date_range_with_from_applies_filter(self):
        qs = _make_queryset()
        d_from = date(2024, 1, 1)
        form = _make_form(date_range="custom", date_from=d_from)
        DateRangeService.apply_date_filters(qs, form)
        qs.filter.assert_called()

    def test_custom_date_range_with_to_applies_filter(self):
        qs = _make_queryset()
        d_to = date(2024, 6, 30)
        form = _make_form(date_range="custom", date_to=d_to)
        DateRangeService.apply_date_filters(qs, form)
        qs.filter.assert_called()

    def test_preset_range_applies_filter(self):
        qs = _make_queryset()
        form = _make_form(date_range="12months")
        DateRangeService.apply_date_filters(qs, form)
        qs.filter.assert_called()

    def test_empty_date_range_no_filtering(self):
        qs = _make_queryset()
        form = _make_form(date_range="")
        result = DateRangeService.apply_date_filters(qs, form)
        qs.filter.assert_not_called()


class TestApplyDateFiltersWithTimezone:
    """Tests for DateRangeService.apply_date_filters_with_timezone."""

    def test_invalid_form_returns_queryset_unchanged(self):
        qs = _make_queryset()
        form = _make_form(valid=False)
        DateRangeService.apply_date_filters_with_timezone(qs, form)
        qs.filter.assert_not_called()

    def test_all_date_range_no_filtering(self):
        qs = _make_queryset()
        form = _make_form(date_range="all")
        DateRangeService.apply_date_filters_with_timezone(qs, form)
        qs.filter.assert_not_called()

    def test_custom_date_range_with_from_applies_filter(self):
        qs = _make_queryset()
        d_from = date(2024, 1, 1)
        form = _make_form(date_range="custom", date_from=d_from)
        DateRangeService.apply_date_filters_with_timezone(qs, form)
        qs.filter.assert_called()

    def test_custom_date_range_with_to_applies_filter(self):
        qs = _make_queryset()
        d_to = date(2024, 6, 30)
        form = _make_form(date_range="custom", date_to=d_to)
        DateRangeService.apply_date_filters_with_timezone(qs, form)
        qs.filter.assert_called()

    def test_preset_range_applies_filter(self):
        qs = _make_queryset()
        form = _make_form(date_range="3months")
        DateRangeService.apply_date_filters_with_timezone(qs, form)
        qs.filter.assert_called()


class TestCleanUrlParametersEdgeCases:
    """Additional tests for DateRangeService.clean_url_parameters edge cases."""

    def _make_querydict(self, params):
        from django.http import QueryDict
        qd = QueryDict(mutable=True)
        qd.update(params)
        return qd

    def test_date_range_with_empty_value_preserved(self):
        qd = self._make_querydict({"date_range": "", "status": "open"})
        clean, has_empty = DateRangeService.clean_url_parameters(qd)
        # date_range key is always preserved even if empty
        assert "date_range" in clean

    def test_non_empty_params_not_flagged(self):
        qd = self._make_querydict({"status": "open", "date_range": "6months"})
        clean, has_empty = DateRangeService.clean_url_parameters(qd)
        assert has_empty is False
