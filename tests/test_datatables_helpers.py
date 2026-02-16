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
Tests for pure-logic helper functions in application/datatables_views.py
"""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from application.datatables_views import (
    DataTablesServerSide,
    _color_for_value,
    _to_date_str,
    _build_filter_url,
    _filter_link,
    _optional_filter_link,
    _STATUS_BADGE_MAP,
    _STATUS_BADGE_DEFAULT,
    _RESOLUTION_THRESHOLDS,
    _OVERDUE_THRESHOLDS,
)


class TestColorForValue:
    """Tests for _color_for_value."""

    def test_value_at_lower_threshold(self):
        thresholds = [(5, "text-success"), (10, "text-warning")]
        result = _color_for_value(3, thresholds, "text-danger")
        assert result == "text-success"

    def test_value_at_boundary(self):
        thresholds = [(5, "text-success"), (10, "text-warning")]
        result = _color_for_value(5, thresholds, "text-danger")
        assert result == "text-success"

    def test_value_at_second_threshold(self):
        thresholds = [(5, "text-success"), (10, "text-warning")]
        result = _color_for_value(7, thresholds, "text-danger")
        assert result == "text-warning"

    def test_value_above_all_thresholds_returns_fallback(self):
        thresholds = [(5, "text-success"), (10, "text-warning")]
        result = _color_for_value(15, thresholds, "text-danger")
        assert result == "text-danger"

    def test_resolution_thresholds_5_days(self):
        result = _color_for_value(4, _RESOLUTION_THRESHOLDS, "text-danger")
        assert result == "text-success"

    def test_resolution_thresholds_over_10_days(self):
        result = _color_for_value(11, _RESOLUTION_THRESHOLDS, "text-danger")
        assert result == "text-danger"

    def test_overdue_thresholds_2_days(self):
        result = _color_for_value(
            1, _OVERDUE_THRESHOLDS, "fw-bold text-white bg-danger px-2 py-1 rounded"
        )
        assert "text-warning" in result


class TestToDateStr:
    """Tests for _to_date_str."""

    def test_date_object_formatted(self):
        d = date(2024, 6, 15)
        assert _to_date_str(d) == "2024-06-15"

    def test_datetime_object_formatted(self):
        dt = datetime(2024, 6, 15, 10, 30)
        assert _to_date_str(dt) == "2024-06-15"

    def test_padding_single_digit_month(self):
        d = date(2024, 3, 5)
        assert _to_date_str(d) == "2024-03-05"


class TestBuildFilterUrl:
    """Tests for _build_filter_url."""

    def test_basic_url_with_filter(self):
        result = _build_filter_url("/enquiries/", {}, status="open")
        assert "/enquiries/?" in result
        assert "status=open" in result

    def test_preserves_existing_filters(self):
        result = _build_filter_url(
            "/enquiries/", {"date_range": "12months"}, status="open"
        )
        assert "date_range=12months" in result
        assert "status=open" in result

    def test_overrides_existing_filter(self):
        result = _build_filter_url("/enquiries/", {"status": "closed"}, status="open")
        assert "status=open" in result

    def test_empty_filters(self):
        result = _build_filter_url("/enquiries/", None, page=2)
        assert "page=2" in result


class TestFilterLink:
    """Tests for _filter_link."""

    def test_returns_anchor_tag(self):
        result = _filter_link(
            "/enquiries/", {}, {"status": "open"}, "Open", "Filter by open"
        )
        assert "<a " in result
        assert "</a>" in result
        assert "Open" in result

    def test_includes_href(self):
        result = _filter_link("/enquiries/", {}, {"status": "open"}, "Open", "Filter")
        assert "href=" in result
        assert "status=open" in result

    def test_escapes_display_text(self):
        result = _filter_link("/enquiries/", {}, {"status": "open"}, "<script>", "bad")
        assert "<script>" not in result

    def test_includes_title(self):
        result = _filter_link("/enquiries/", {}, {}, "Text", "My tooltip")
        assert 'title="My tooltip"' in result


class TestOptionalFilterLink:
    """Tests for _optional_filter_link."""

    def test_returns_fallback_for_none_object(self):
        result = _optional_filter_link(
            "/enquiries/", {}, None, "member", "name", "Member"
        )
        assert result == "Not assigned"

    def test_custom_fallback_text(self):
        result = _optional_filter_link(
            "/enquiries/", {}, None, "member", "name", "Member", "N/A"
        )
        assert result == "N/A"

    def test_returns_link_for_valid_object(self):
        obj = MagicMock()
        obj.id = 42
        obj.name = "John Smith"
        result = _optional_filter_link(
            "/enquiries/", {}, obj, "member", "name", "Filter by member"
        )
        assert "<a " in result
        assert "John Smith" in result

    def test_link_includes_object_id(self):
        obj = MagicMock()
        obj.id = 99
        obj.name = "Test"
        result = _optional_filter_link(
            "/enquiries/", {}, obj, "section", "name", "Section"
        )
        assert "member=99" not in result  # Wrong key
        assert "section=99" in result


class TestStatusBadgeConstants:
    """Tests for status badge map constants."""

    def test_new_status_in_map(self):
        assert "new" in _STATUS_BADGE_MAP

    def test_open_status_in_map(self):
        assert "open" in _STATUS_BADGE_MAP

    def test_closed_status_in_map(self):
        assert "closed" in _STATUS_BADGE_MAP

    def test_default_badge_is_secondary(self):
        css_class, _ = _STATUS_BADGE_DEFAULT
        assert "secondary" in css_class


# ---------------------------------------------------------------------------
# Tests for DataTablesServerSide methods
# ---------------------------------------------------------------------------


def _make_request_data(**overrides):
    """Build a minimal DataTables request_data dict with sensible defaults."""
    data = {
        "draw": "1",
        "start": "0",
        "length": "10",
        "search[value]": "",
        "order[0][column]": "9",
        "order[0][dir]": "desc",
    }
    data.update(overrides)
    return data


def _make_dt(request_data=None, **kw):
    """Create a DataTablesServerSide instance with a dummy request."""
    request = MagicMock()
    request.GET = request_data or {}
    return DataTablesServerSide(request, request_data=request_data or kw or None)


class TestDataTablesInit:
    """Tests for DataTablesServerSide.__init__."""

    def test_defaults_when_no_data(self):
        request = MagicMock()
        request.GET = {}
        dt = DataTablesServerSide(request)
        assert dt.draw == 1
        assert dt.start == 0
        assert dt.length == 10
        assert dt.search_value == ""
        assert dt.order_column == 9
        assert dt.order_dir == "desc"

    def test_length_minus_one_becomes_10000(self):
        data = _make_request_data(length="-1")
        dt = _make_dt(data)
        assert dt.length == 10000

    def test_start_negative_clamped_to_zero(self):
        data = _make_request_data(start="-5")
        dt = _make_dt(data)
        assert dt.start == 0

    def test_custom_draw(self):
        data = _make_request_data(draw="7")
        dt = _make_dt(data)
        assert dt.draw == 7

    def test_custom_start(self):
        data = _make_request_data(start="50")
        dt = _make_dt(data)
        assert dt.start == 50

    def test_custom_length(self):
        data = _make_request_data(length="25")
        dt = _make_dt(data)
        assert dt.length == 25

    def test_custom_search_value(self):
        data = _make_request_data(**{"search[value]": "  hello  "})
        dt = _make_dt(data)
        assert dt.search_value == "hello"

    def test_custom_order_column(self):
        data = _make_request_data(**{"order[0][column]": "3"})
        dt = _make_dt(data)
        assert dt.order_column == 3

    def test_custom_order_dir_asc(self):
        data = _make_request_data(**{"order[0][dir]": "asc"})
        dt = _make_dt(data)
        assert dt.order_dir == "asc"

    def test_request_data_none_falls_back_to_get(self):
        request = MagicMock()
        request.GET = {
            "draw": "4",
            "start": "10",
            "length": "20",
            "search[value]": "",
            "order[0][column]": "0",
            "order[0][dir]": "asc",
        }
        dt = DataTablesServerSide(request, request_data=None)
        assert dt.draw == 4
        assert dt.start == 10
        assert dt.length == 20


class TestGetStatusBadge:
    """Tests for DataTablesServerSide._get_status_badge."""

    def test_new_status(self):
        enquiry = MagicMock()
        enquiry.status = "new"
        enquiry.get_status_display.return_value = "New"
        css, text = DataTablesServerSide._get_status_badge(enquiry)
        assert css == "bg-primary"
        assert text == "Open"

    def test_open_status_uses_display(self):
        enquiry = MagicMock()
        enquiry.status = "open"
        enquiry.get_status_display.return_value = "In Progress"
        css, text = DataTablesServerSide._get_status_badge(enquiry)
        assert css == "bg-primary"
        assert text == "In Progress"

    def test_closed_status_uses_display(self):
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.get_status_display.return_value = "Closed"
        css, text = DataTablesServerSide._get_status_badge(enquiry)
        assert css == "bg-success"
        assert text == "Closed"

    def test_unknown_status_uses_default(self):
        enquiry = MagicMock()
        enquiry.status = "archived"
        enquiry.get_status_display.return_value = "Archived"
        css, text = DataTablesServerSide._get_status_badge(enquiry)
        assert css == "bg-secondary"
        assert text == "Archived"


class TestGetResolutionTimeHtml:
    """Tests for DataTablesServerSide._get_resolution_time_html."""

    def test_not_closed_returns_dash(self):
        enquiry = MagicMock()
        enquiry.status = "open"
        assert DataTablesServerSide._get_resolution_time_html(enquiry) == "-"

    def test_closed_but_no_closed_at_returns_dash(self):
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = None
        assert DataTablesServerSide._get_resolution_time_html(enquiry) == "-"

    @patch("application.utils.calculate_business_days", return_value=None)
    def test_closed_with_none_business_days_returns_dash(self, mock_calc):
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = datetime(2026, 2, 10, 12, 0)
        enquiry.created_at = datetime(2026, 2, 5, 9, 0)
        assert DataTablesServerSide._get_resolution_time_html(enquiry) == "-"

    @patch("application.utils.calculate_business_days", return_value=3)
    def test_closed_short_resolution_text_success(self, mock_calc):
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = datetime(2026, 2, 10, 12, 0)
        enquiry.created_at = datetime(2026, 2, 5, 9, 0)
        result = DataTablesServerSide._get_resolution_time_html(enquiry)
        assert "text-success" in result
        assert "3" in result

    @patch("application.utils.calculate_business_days", return_value=12)
    def test_closed_long_resolution_text_danger(self, mock_calc):
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = datetime(2026, 2, 10, 12, 0)
        enquiry.created_at = datetime(2026, 1, 20, 9, 0)
        result = DataTablesServerSide._get_resolution_time_html(enquiry)
        assert "text-danger" in result
        assert "12" in result


class TestGetActionsHtml:
    """Tests for DataTablesServerSide._get_actions_html."""

    @patch("application.datatables_views.reverse")
    def test_open_enquiry_has_edit_and_close(self, mock_reverse):
        mock_reverse.side_effect = lambda name, args=None: (
            f"/enquiry/{args[0]}/" if "detail" in name else f"/enquiry/{args[0]}/edit/"
        )
        enquiry = MagicMock()
        enquiry.id = 42
        enquiry.reference = "REF-001"
        enquiry.title = "Test enquiry"
        enquiry.status = "open"
        result = DataTablesServerSide._get_actions_html(enquiry)
        assert "View" in result
        assert "Edit" in result
        assert "Close" in result
        assert "Re-open" not in result

    @patch("application.datatables_views.reverse")
    def test_closed_enquiry_has_reopen_no_edit(self, mock_reverse):
        mock_reverse.return_value = "/enquiry/42/"
        enquiry = MagicMock()
        enquiry.id = 42
        enquiry.reference = "REF-002"
        enquiry.title = "Closed enquiry"
        enquiry.status = "closed"
        result = DataTablesServerSide._get_actions_html(enquiry)
        assert "View" in result
        assert "Re-open" in result
        assert "Edit" not in result
        assert "Close</button>" not in result

    @patch("application.datatables_views.reverse")
    def test_view_button_has_correct_url(self, mock_reverse):
        mock_reverse.return_value = "/enquiry/99/"
        enquiry = MagicMock()
        enquiry.id = 99
        enquiry.reference = "REF-099"
        enquiry.title = "Detail test"
        enquiry.status = "closed"
        result = DataTablesServerSide._get_actions_html(enquiry)
        assert 'href="/enquiry/99/"' in result

    @patch("application.datatables_views.reverse")
    def test_actions_escapes_reference(self, mock_reverse):
        mock_reverse.return_value = "/enquiry/1/"
        enquiry = MagicMock()
        enquiry.id = 1
        enquiry.reference = '<script>alert("xss")</script>'
        enquiry.title = "Normal title"
        enquiry.status = "open"
        result = DataTablesServerSide._get_actions_html(enquiry)
        assert "<script>" not in result


class TestGetOverdueInfo:
    """Tests for DataTablesServerSide._get_overdue_info."""

    def test_future_due_date_not_overdue(self):
        enquiry = MagicMock()
        enquiry.due_date = date(2026, 3, 1)
        enquiry.status = "open"
        due, is_overdue, html = DataTablesServerSide._get_overdue_info(
            enquiry, date(2026, 2, 12)
        )
        assert due == date(2026, 3, 1)
        assert is_overdue is False
        assert html == "-"

    def test_past_due_date_but_closed_not_overdue(self):
        enquiry = MagicMock()
        enquiry.due_date = date(2026, 1, 1)
        enquiry.status = "closed"
        due, is_overdue, html = DataTablesServerSide._get_overdue_info(
            enquiry, date(2026, 2, 12)
        )
        assert is_overdue is False
        assert html == "-"

    @patch("application.utils.calculate_business_days", return_value=5)
    def test_past_due_date_open_overdue(self, mock_calc):
        enquiry = MagicMock()
        enquiry.due_date = date(2026, 1, 20)
        enquiry.status = "open"
        due, is_overdue, html = DataTablesServerSide._get_overdue_info(
            enquiry, date(2026, 2, 12)
        )
        assert is_overdue is True
        assert "5" in html
        assert "overdue" in html.lower()

    def test_datetime_due_date_extracts_date(self):
        enquiry = MagicMock()
        enquiry.due_date = datetime(2026, 3, 15, 10, 0)
        enquiry.status = "open"
        due, is_overdue, html = DataTablesServerSide._get_overdue_info(
            enquiry, date(2026, 2, 12)
        )
        assert due == date(2026, 3, 15)
        assert is_overdue is False

    @patch("application.utils.calculate_business_days", return_value=0)
    def test_overdue_zero_business_days_returns_dash(self, mock_calc):
        enquiry = MagicMock()
        enquiry.due_date = date(2026, 2, 11)
        enquiry.status = "open"
        _, is_overdue, html = DataTablesServerSide._get_overdue_info(
            enquiry, date(2026, 2, 12)
        )
        assert html == "-"

    @patch("application.utils.calculate_business_days", return_value=None)
    def test_overdue_none_business_days_returns_dash(self, mock_calc):
        enquiry = MagicMock()
        enquiry.due_date = date(2026, 2, 10)
        enquiry.status = "open"
        _, is_overdue, html = DataTablesServerSide._get_overdue_info(
            enquiry, date(2026, 2, 12)
        )
        assert html == "-"


class TestExtractCurrentFilters:
    """Tests for DataTablesServerSide._extract_current_filters."""

    def test_no_cleaned_data_returns_empty(self):
        form = MagicMock(spec=[])  # no attributes at all
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {}

    def test_cleaned_data_none_returns_empty(self):
        form = MagicMock()
        form.cleaned_data = None
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {}

    def test_empty_values_excluded(self):
        form = MagicMock()
        form.cleaned_data = {"status": "", "member": None, "section": "all"}
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {}

    def test_model_instance_converted_to_id(self):
        obj = MagicMock()
        obj.id = 42
        form = MagicMock()
        form.cleaned_data = {"member": obj}
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {"member": "42"}

    def test_boolean_true_converts_to_on(self):
        form = MagicMock()
        form.cleaned_data = {"overdue_only": True}
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {"overdue_only": "on"}

    def test_boolean_false_excluded(self):
        form = MagicMock()
        form.cleaned_data = {"overdue_only": False}
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {}

    def test_string_value_kept(self):
        form = MagicMock()
        form.cleaned_data = {"date_range": "12months"}
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {"date_range": "12months"}

    def test_mixed_values(self):
        obj = MagicMock()
        obj.id = 7
        form = MagicMock()
        form.cleaned_data = {
            "status": "open",
            "member": obj,
            "search": "",
            "overdue_only": True,
            "section": None,
        }
        result = DataTablesServerSide._extract_current_filters(form)
        assert result == {
            "status": "open",
            "member": "7",
            "overdue_only": "on",
        }


class TestApplyOrdering:
    """Tests for DataTablesServerSide.apply_ordering."""

    def test_valid_column_asc(self):
        data = _make_request_data(**{"order[0][column]": "0", "order[0][dir]": "asc"})
        dt = _make_dt(data)
        qs = MagicMock()
        qs.order_by.return_value = qs
        result = dt.apply_ordering(qs)
        qs.order_by.assert_called_once_with("reference")
        assert result is qs

    def test_valid_column_desc(self):
        data = _make_request_data(**{"order[0][column]": "1", "order[0][dir]": "desc"})
        dt = _make_dt(data)
        qs = MagicMock()
        qs.order_by.return_value = qs
        dt.apply_ordering(qs)
        qs.order_by.assert_called_once_with("-title")

    def test_none_column_defaults_to_created_at(self):
        # Column 12 maps to None (Overdue Days - calculated)
        data = _make_request_data(**{"order[0][column]": "12"})
        dt = _make_dt(data)
        qs = MagicMock()
        qs.order_by.return_value = qs
        dt.apply_ordering(qs)
        qs.order_by.assert_called_once_with("-created_at")

    def test_out_of_range_column_defaults_to_created_at(self):
        data = _make_request_data(**{"order[0][column]": "99"})
        dt = _make_dt(data)
        qs = MagicMock()
        qs.order_by.return_value = qs
        dt.apply_ordering(qs)
        qs.order_by.assert_called_once_with("-created_at")

    def test_column_status_desc(self):
        data = _make_request_data(**{"order[0][column]": "7", "order[0][dir]": "desc"})
        dt = _make_dt(data)
        qs = MagicMock()
        qs.order_by.return_value = qs
        dt.apply_ordering(qs)
        qs.order_by.assert_called_once_with("-status")
