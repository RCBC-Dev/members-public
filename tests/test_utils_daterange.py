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
Tests for DateRangeUtility and related functions in application/utils.py
"""

import pytest
from django.utils import timezone
from application.utils import (
    DateRangeUtility,
    generate_last_months,
    calculate_month_range_from_keys,
    _check_file_size,
    _check_extension,
    _check_mime_type,
    _address_field_contains_target,
    _has_external_warning_banner,
    _normalize_plain_text,
)


class TestDateRangeUtility:
    """Tests for DateRangeUtility."""

    def test_generate_month_periods_returns_correct_count(self):
        months, keys, date_from, date_to = DateRangeUtility.generate_month_periods(12)
        assert len(months) == 12
        assert len(keys) == 12

    def test_generate_month_periods_keys_format(self):
        _, keys, _, _ = DateRangeUtility.generate_month_periods(3)
        for key in keys:
            parts = key.split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 4  # year
            assert len(parts[1]) == 2  # month

    def test_generate_month_periods_dates_are_ordered(self):
        _, _, date_from, date_to = DateRangeUtility.generate_month_periods(6)
        assert date_from < date_to

    def test_calculate_range_from_keys_empty(self):
        result = DateRangeUtility.calculate_range_from_keys([])
        assert result == (None, None)

    def test_calculate_range_from_keys_single_month(self):
        date_from, date_to = DateRangeUtility.calculate_range_from_keys(["2024-06"])
        assert date_from is not None
        assert date_to is not None
        assert date_from < date_to

    def test_calculate_range_from_keys_december(self):
        # December should roll over to January next year
        date_from, date_to = DateRangeUtility.calculate_range_from_keys(["2024-12"])
        assert date_to.year == 2025
        assert date_to.month == 1

    def test_calculate_range_from_keys_multiple_months(self):
        keys = ["2024-01", "2024-02", "2024-03"]
        date_from, date_to = DateRangeUtility.calculate_range_from_keys(keys)
        assert date_from.month == 1
        assert date_to.month == 4  # first day of month after last

    def test_get_filter_dates_all_returns_none(self):
        d_from, d_to = DateRangeUtility.get_filter_dates("all")
        assert d_from is None
        assert d_to is None


class TestBackwardCompatFunctions:
    """Tests for module-level backward compat functions."""

    def test_generate_last_months_returns_tuple(self):
        months, keys = generate_last_months(6)
        assert len(months) == 6
        assert len(keys) == 6

    def test_calculate_month_range_from_keys(self):
        d_from, d_to = calculate_month_range_from_keys(["2024-01", "2024-06"])
        assert d_from is not None
        assert d_to is not None


class TestCheckFileSize:
    """Tests for _check_file_size."""

    def test_does_not_raise_for_small_file(self):
        _check_file_size(100, max_size_mb=2)  # should not raise

    def test_raises_for_oversized_file(self):
        with pytest.raises(ValueError, match="exceeds"):
            _check_file_size(10 * 1024 * 1024, max_size_mb=2)


class TestCheckExtension:
    """Tests for _check_extension."""

    def test_does_not_raise_for_allowed_extension(self):
        _check_extension("photo.jpg", {".jpg", ".png"})  # should not raise

    def test_raises_for_disallowed_extension(self):
        with pytest.raises(ValueError, match="not allowed"):
            _check_extension("virus.exe", {".jpg", ".png"})

    def test_case_insensitive_check(self):
        _check_extension("photo.JPG", {".jpg"})  # should not raise


class TestCheckMimeType:
    """Tests for _check_mime_type (logs warning, never raises)."""

    def test_matching_mime_does_not_log_warning(self):
        # Should not raise for correct MIME type
        _check_mime_type("photo.jpg", "image/jpeg")

    def test_mismatched_mime_does_not_raise(self):
        # Should only log a warning, not raise
        _check_mime_type("photo.jpg", "application/octet-stream")


class TestAddressFieldContainsTarget:
    """Tests for _address_field_contains_target."""

    def test_returns_false_for_none(self):
        assert _address_field_contains_target(None) is False

    def test_returns_false_for_empty(self):
        assert _address_field_contains_target("") is False

    def test_returns_true_when_target_present(self):
        field = "memberenquiries@redcar-cleveland.gov.uk"
        assert _address_field_contains_target(field) is True

    def test_returns_false_for_different_address(self):
        assert _address_field_contains_target("other@example.com") is False


class TestHasExternalWarningBanner:
    """Tests for _has_external_warning_banner."""

    def test_returns_false_for_none(self):
        assert _has_external_warning_banner(None) is False

    def test_returns_false_for_empty(self):
        assert _has_external_warning_banner("") is False

    def test_returns_true_for_warning_banner(self):
        text = "WARNING: This email came from outside of the organisation. Do not provide login or password details. Always be cautious opening links and attachments wherever the email appears to come from. If you have any doubts about this email, contact ICT.\n\nHello"
        assert _has_external_warning_banner(text) is True

    def test_returns_false_for_regular_text(self):
        text = "Hello this is a regular email message with no banner"
        assert _has_external_warning_banner(text) is False


class TestNormalizePlainText:
    """Tests for _normalize_plain_text."""

    def test_normalizes_windows_line_endings(self):
        result = _normalize_plain_text("line1\r\nline2")
        assert "\r\n" not in result
        assert "line1\nline2" == result

    def test_normalizes_old_mac_line_endings(self):
        result = _normalize_plain_text("line1\rline2")
        assert "\r" not in result

    def test_collapses_whitespace_only_lines(self):
        result = _normalize_plain_text("line1\n   \nline2")
        assert "   " not in result

    def test_preserves_normal_text(self):
        result = _normalize_plain_text("hello world")
        assert result == "hello world"
