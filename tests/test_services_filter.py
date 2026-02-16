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
Tests for pure-logic static methods in application/services.py EnquiryFilterService
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch, call
from application.services import EnquiryFilterService


class TestBuildStatusPrefix:
    """Tests for EnquiryFilterService._build_status_prefix."""

    def test_open_status_returns_open_prefix(self):
        result = EnquiryFilterService._build_status_prefix({"status": "open"})
        assert result == "Open Members Enquiries"

    def test_closed_status_returns_closed_prefix(self):
        result = EnquiryFilterService._build_status_prefix({"status": "closed"})
        assert result == "Closed Members Enquiries"

    def test_no_status_returns_plain_prefix(self):
        result = EnquiryFilterService._build_status_prefix({})
        assert result == "Members Enquiries"

    def test_unknown_status_returns_plain_prefix(self):
        result = EnquiryFilterService._build_status_prefix({"status": "pending"})
        assert result == "Members Enquiries"

    def test_empty_status_returns_plain_prefix(self):
        result = EnquiryFilterService._build_status_prefix({"status": ""})
        assert result == "Members Enquiries"


class TestBuildDateRangeSuffix:
    """Tests for EnquiryFilterService._build_date_range_suffix."""

    def test_3months_returns_predefined_label(self):
        result = EnquiryFilterService._build_date_range_suffix(
            {"date_range": "3months"}
        )
        assert "3 months" in result

    def test_6months_returns_predefined_label(self):
        result = EnquiryFilterService._build_date_range_suffix(
            {"date_range": "6months"}
        )
        assert "6 months" in result

    def test_12months_returns_predefined_label(self):
        result = EnquiryFilterService._build_date_range_suffix(
            {"date_range": "12months"}
        )
        assert "12 months" in result

    def test_all_returns_all_time_label(self):
        result = EnquiryFilterService._build_date_range_suffix({"date_range": "all"})
        assert "All Time" in result

    def test_custom_with_both_dates_includes_both(self):
        result = EnquiryFilterService._build_date_range_suffix(
            {
                "date_range": "custom",
                "date_from": date(2024, 1, 1),
                "date_to": date(2024, 6, 30),
            }
        )
        assert "01/01/2024" in result
        assert "30/06/2024" in result

    def test_custom_with_only_date_from(self):
        result = EnquiryFilterService._build_date_range_suffix(
            {
                "date_range": "custom",
                "date_from": date(2024, 1, 1),
                "date_to": None,
            }
        )
        assert "from" in result
        assert "01/01/2024" in result

    def test_custom_with_only_date_to(self):
        result = EnquiryFilterService._build_date_range_suffix(
            {
                "date_range": "custom",
                "date_from": None,
                "date_to": date(2024, 6, 30),
            }
        )
        assert "until" in result
        assert "30/06/2024" in result

    def test_custom_without_dates_returns_empty(self):
        result = EnquiryFilterService._build_date_range_suffix(
            {
                "date_range": "custom",
                "date_from": None,
                "date_to": None,
            }
        )
        assert result == ""

    def test_empty_date_range_treated_as_custom(self):
        # Empty string date_range is treated as custom
        result = EnquiryFilterService._build_date_range_suffix(
            {
                "date_range": "",
                "date_from": None,
                "date_to": None,
            }
        )
        assert result == ""

    def test_unknown_non_custom_range_returns_empty(self):
        # Non-empty, non-predefined, non-custom range returns empty
        result = EnquiryFilterService._build_date_range_suffix(
            {
                "date_range": "quarterly",
            }
        )
        assert result == ""


class TestDateRangeLabels:
    """Tests for EnquiryFilterService._DATE_RANGE_LABELS constant."""

    def test_3months_label_defined(self):
        assert "3months" in EnquiryFilterService._DATE_RANGE_LABELS

    def test_12months_label_defined(self):
        assert "12months" in EnquiryFilterService._DATE_RANGE_LABELS

    def test_all_label_defined(self):
        assert "all" in EnquiryFilterService._DATE_RANGE_LABELS


class TestStatusLabels:
    """Tests for EnquiryFilterService._STATUS_LABELS constant."""

    def test_open_label_defined(self):
        assert "open" in EnquiryFilterService._STATUS_LABELS

    def test_closed_label_defined(self):
        assert "closed" in EnquiryFilterService._STATUS_LABELS
