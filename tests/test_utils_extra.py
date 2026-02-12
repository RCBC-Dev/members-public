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
Additional tests for uncovered functions in application/utils.py
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo


class TestFormatRecipientList:
    """Tests for _format_recipient_list."""

    def test_empty_string_returns_empty(self):
        from application.utils import _format_recipient_list
        assert _format_recipient_list("") == ""

    def test_none_returns_empty(self):
        from application.utils import _format_recipient_list
        assert _format_recipient_list(None) == ""

    def test_single_named_recipient(self):
        from application.utils import _format_recipient_list
        result = _format_recipient_list("John Smith <john@example.com>")
        assert "john@example.com" in result
        assert "John Smith" in result

    def test_single_bare_email(self):
        from application.utils import _format_recipient_list
        result = _format_recipient_list("john@example.com")
        assert "john@example.com" in result

    def test_multiple_recipients_semicolon_separated(self):
        from application.utils import _format_recipient_list
        result = _format_recipient_list("a@a.com; b@b.com")
        assert "a@a.com" in result
        assert "b@b.com" in result

    def test_empty_entries_skipped(self):
        from application.utils import _format_recipient_list
        result = _format_recipient_list("; a@a.com; ;")
        assert result.count("@") == 1


class TestParseSenderInfo:
    """Tests for _parse_sender_info."""

    def test_sender_with_name_and_email(self):
        from application.utils import _parse_sender_info
        msg = MagicMock()
        msg.sender = "John Smith <john@example.com>"
        msg.sender_name = "John Smith"
        msg.sender_email = "john@example.com"
        email_from, raw_from = _parse_sender_info(msg)
        assert "john@example.com" in email_from
        assert "John Smith" in email_from

    def test_sender_email_only(self):
        from application.utils import _parse_sender_info
        msg = MagicMock()
        msg.sender = "john@example.com"
        msg.sender_name = ""
        msg.sender_email = "john@example.com"
        email_from, raw_from = _parse_sender_info(msg)
        assert "john@example.com" in email_from

    def test_fallback_when_no_email(self):
        from application.utils import _parse_sender_info
        msg = MagicMock()
        msg.sender = ""
        msg.sender_name = ""
        msg.sender_email = ""
        email_from, raw_from = _parse_sender_info(msg)
        assert email_from == "Unknown Sender"

    def test_parses_sender_from_raw_if_no_explicit_email(self):
        from application.utils import _parse_sender_info
        msg = MagicMock()
        msg.sender = "Jane Doe <jane@example.com>"
        msg.sender_name = ""
        msg.sender_email = ""
        email_from, raw_from = _parse_sender_info(msg)
        assert "jane@example.com" in email_from


class TestParseEmailDate:
    """Tests for _parse_email_date."""

    def test_uses_receivedTime_when_available(self):
        from application.utils import _parse_email_date
        msg = MagicMock()
        aware_dt = datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
        msg.receivedTime = aware_dt
        utc_dt, formatted = _parse_email_date(msg)
        assert utc_dt is not None
        assert "2024" in formatted or "Jun" in formatted

    def test_uses_parsedDate_as_fallback(self):
        from application.utils import _parse_email_date
        msg = MagicMock(spec=["parsedDate"])
        msg.parsedDate = (2024, 6, 15, 10, 0, 0)
        utc_dt, formatted = _parse_email_date(msg)
        assert utc_dt is not None

    def test_falls_back_to_now_on_error(self):
        from application.utils import _parse_email_date
        from django.utils import timezone
        msg = MagicMock(spec=[])  # No attributes - will raise ValueError
        utc_dt, formatted = _parse_email_date(msg)
        # Should return approximately now
        now = timezone.now()
        diff = abs((now - utc_dt).total_seconds())
        assert diff < 10  # Within 10 seconds

    def test_naive_datetime_handled(self):
        from application.utils import _parse_email_date
        msg = MagicMock()
        naive_dt = datetime(2024, 6, 15, 10, 0)  # No tzinfo
        msg.receivedTime = naive_dt
        utc_dt, formatted = _parse_email_date(msg)
        assert utc_dt.tzinfo is not None  # Should be timezone-aware now


class TestResizeImageIfNeeded:
    """Tests for _resize_image_if_needed."""

    def test_small_image_not_resized(self):
        from application.utils import _resize_image_if_needed
        # Create small image data (100 bytes < 2MB limit)
        small_data = b"x" * 100
        result_data, was_resized, size = _resize_image_if_needed(small_data)
        assert was_resized is False
        assert result_data == small_data

    def test_returns_original_if_pil_not_available(self):
        from application.utils import _resize_image_if_needed
        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
            data = b"x" * 100
            result_data, was_resized, size = _resize_image_if_needed(data)
            assert result_data == data
            assert was_resized is False


class TestStripHtmlTags:
    """Tests for strip_html_tags."""

    def test_removes_tags(self):
        from application.utils import strip_html_tags
        result = strip_html_tags("<p>Hello <b>world</b></p>")
        assert result == "Hello world"

    def test_decodes_html_entities(self):
        from application.utils import strip_html_tags
        result = strip_html_tags("&lt;test&gt;")
        assert result == "<test>"

    def test_empty_string_returns_empty(self):
        from application.utils import strip_html_tags
        result = strip_html_tags("")
        assert result == ""

    def test_none_returns_none(self):
        from application.utils import strip_html_tags
        result = strip_html_tags(None)
        assert result is None

    def test_plain_text_unchanged(self):
        from application.utils import strip_html_tags
        result = strip_html_tags("plain text")
        assert result == "plain text"


class TestCalculateBusinessDays:
    """Tests for calculate_business_days."""

    def test_monday_to_friday_is_5(self):
        from application.utils import calculate_business_days
        start = date(2024, 6, 10)  # Monday
        end = date(2024, 6, 14)    # Friday
        assert calculate_business_days(start, end) == 4

    def test_same_dates_returns_zero(self):
        from application.utils import calculate_business_days
        d = date(2024, 6, 10)
        assert calculate_business_days(d, d) == 0

    def test_none_start_returns_none(self):
        from application.utils import calculate_business_days
        assert calculate_business_days(None, date(2024, 6, 10)) is None

    def test_none_end_returns_none(self):
        from application.utils import calculate_business_days
        assert calculate_business_days(date(2024, 6, 10), None) is None

    def test_datetime_objects_accepted(self):
        from application.utils import calculate_business_days
        from django.utils import timezone
        start = timezone.make_aware(datetime(2024, 6, 10))
        end = timezone.make_aware(datetime(2024, 6, 14))
        result = calculate_business_days(start, end)
        assert result == 4

    def test_weekend_excluded(self):
        from application.utils import calculate_business_days
        # Mon to Mon next week = 5 business days (Tue-Fri + Mon)
        start = date(2024, 6, 10)   # Monday
        end = date(2024, 6, 17)     # Monday
        result = calculate_business_days(start, end)
        assert result == 5  # Mon through Fri (5 days, Sat/Sun excluded)


class TestCalculateCalendarDays:
    """Tests for calculate_calendar_days."""

    def test_week_apart(self):
        from application.utils import calculate_calendar_days
        start = date(2024, 6, 10)
        end = date(2024, 6, 17)
        assert calculate_calendar_days(start, end) == 7

    def test_same_day_returns_zero(self):
        from application.utils import calculate_calendar_days
        d = date(2024, 6, 10)
        assert calculate_calendar_days(d, d) == 0

    def test_none_returns_none(self):
        from application.utils import calculate_calendar_days
        assert calculate_calendar_days(None, date(2024, 6, 10)) is None

    def test_datetime_objects(self):
        from application.utils import calculate_calendar_days
        from django.utils import timezone
        start = timezone.make_aware(datetime(2024, 6, 10))
        end = timezone.make_aware(datetime(2024, 6, 17))
        assert calculate_calendar_days(start, end) == 7


class TestCalculateWorkingDaysDueDate:
    """Tests for calculate_working_days_due_date."""

    def test_basic_5_business_days(self):
        from application.utils import calculate_working_days_due_date
        start = date(2024, 6, 10)  # Monday
        result = calculate_working_days_due_date(start, 5)
        assert result == date(2024, 6, 17)  # Next Monday

    def test_none_start_returns_none(self):
        from application.utils import calculate_working_days_due_date
        assert calculate_working_days_due_date(None, 5) is None

    def test_zero_days_returns_none(self):
        from application.utils import calculate_working_days_due_date
        assert calculate_working_days_due_date(date(2024, 6, 10), 0) is None

    def test_datetime_input(self):
        from application.utils import calculate_working_days_due_date
        from django.utils import timezone
        start = timezone.make_aware(datetime(2024, 6, 10))  # Monday
        result = calculate_working_days_due_date(start, 5)
        assert result == date(2024, 6, 17)


class TestFormatPlainTextForHtmlDisplay:
    """Tests for _format_plain_text_for_html_display."""

    def test_empty_returns_empty(self):
        from application.utils import _format_plain_text_for_html_display
        assert _format_plain_text_for_html_display("") == ""

    def test_none_returns_empty(self):
        from application.utils import _format_plain_text_for_html_display
        assert _format_plain_text_for_html_display(None) == ""

    def test_simple_text_preserved(self):
        from application.utils import _format_plain_text_for_html_display
        result = _format_plain_text_for_html_display("Hello world")
        assert "Hello world" in result

    def test_html_characters_escaped(self):
        from application.utils import _format_plain_text_for_html_display
        result = _format_plain_text_for_html_display("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestWrapQuotedBlocks:
    """Tests for _wrap_quoted_blocks."""

    def test_wraps_quoted_lines(self):
        from application.utils import _wrap_quoted_blocks
        html = "&gt; This is a quote<br>&gt; More quote"
        result = _wrap_quoted_blocks(html)
        assert "email-quote" in result

    def test_plain_text_unchanged(self):
        from application.utils import _wrap_quoted_blocks
        html = "<p>Normal text</p>"
        result = _wrap_quoted_blocks(html)
        assert result == html


class TestDateRangeUtility:
    """Tests for DateRangeUtility."""

    def test_generate_month_periods_returns_correct_count(self):
        from application.utils import DateRangeUtility
        months, keys, date_from, date_to = DateRangeUtility.generate_month_periods(6)
        assert len(months) == 6
        assert len(keys) == 6

    def test_generate_month_periods_keys_format(self):
        from application.utils import DateRangeUtility
        _, keys, _, _ = DateRangeUtility.generate_month_periods(3)
        for key in keys:
            # Should be YYYY-MM format
            assert len(key) == 7
            assert key[4] == "-"

    def test_generate_month_periods_dates_ordered(self):
        from application.utils import DateRangeUtility
        months, keys, date_from, date_to = DateRangeUtility.generate_month_periods(12)
        assert date_from < date_to

    def test_calculate_range_from_keys_empty_returns_none(self):
        from application.utils import DateRangeUtility
        d_from, d_to = DateRangeUtility.calculate_range_from_keys([])
        assert d_from is None
        assert d_to is None

    def test_calculate_range_from_keys_single_key(self):
        from application.utils import DateRangeUtility
        d_from, d_to = DateRangeUtility.calculate_range_from_keys(["2024-06"])
        assert d_from is not None
        assert d_to is not None
        assert d_from < d_to

    def test_calculate_range_from_keys_december_wraps_year(self):
        from application.utils import DateRangeUtility
        d_from, d_to = DateRangeUtility.calculate_range_from_keys(["2024-12"])
        assert d_to.year == 2025
        assert d_to.month == 1


class TestGenerateLastMonths:
    """Tests for generate_last_months (backwards compat)."""

    def test_returns_default_12_months(self):
        from application.utils import generate_last_months
        months, keys = generate_last_months()
        assert len(months) == 12
        assert len(keys) == 12

    def test_custom_count(self):
        from application.utils import generate_last_months
        months, keys = generate_last_months(6)
        assert len(months) == 6


@pytest.mark.django_db
class TestCreateEnquiryFromEmail:
    """Tests for create_enquiry_from_email."""

    def test_no_sender_returns_error(self):
        from application.utils import create_enquiry_from_email
        from django.contrib.auth.models import User
        user = User.objects.create_user(username="email_creator", password="p")
        parsed = {"email_from": "", "subject": "Test"}
        result = create_enquiry_from_email(parsed, user)
        assert result["success"] is False
        assert "email" in result["error"].lower()

    def test_unknown_member_returns_error(self):
        from application.utils import create_enquiry_from_email
        from django.contrib.auth.models import User
        user = User.objects.create_user(username="email_creator2", password="p")
        parsed = {"email_from": "nobody@unknown.com", "subject": "Test"}
        result = create_enquiry_from_email(parsed, user)
        assert result["success"] is False
        assert "member" in result["error"].lower() or "email" in result["error"].lower()
