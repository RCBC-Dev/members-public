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
Tests for pure-logic helper functions in application/class_views.py
"""

import pytest
from unittest.mock import MagicMock, patch
from application.class_views import EnquiryFilterMixin


def _make_mixin():
    """Create a bare EnquiryFilterMixin instance."""
    return EnquiryFilterMixin()


def _make_form(status=None, date_range=None, valid=True):
    """Create a mock filter form."""
    form = MagicMock()
    form.is_valid.return_value = valid
    form.cleaned_data = {
        "status": status or "",
        "date_range": date_range or "",
        "member": None,
        "admin": None,
        "section": None,
        "search": "",
        "overdue_only": False,
    }
    form.data = {
        "status": status or "",
        "date_range": date_range or "",
    }
    return form


class TestGetNoResultsHint:
    """Tests for EnquiryFilterMixin.get_no_results_hint."""

    def test_returns_none_when_results_found(self):
        mixin = _make_mixin()
        form = _make_form()
        result = mixin.get_no_results_hint(form, result_count=5)
        assert result is None

    def test_no_filters_returns_simple_no_results(self):
        mixin = _make_mixin()
        form = _make_form(status="", date_range="")
        hint = mixin.get_no_results_hint(form, result_count=0)
        assert hint == "No results found."

    def test_status_filter_suggests_all_status(self):
        mixin = _make_mixin()
        form = _make_form(status="closed", date_range="")
        hint = mixin.get_no_results_hint(form, result_count=0)
        assert "status" in hint.lower() or "'All Enquiries'" in hint

    def test_date_range_filter_suggests_all_time(self):
        mixin = _make_mixin()
        form = _make_form(status="", date_range="12months")
        hint = mixin.get_no_results_hint(form, result_count=0)
        assert "All time" in hint or "date" in hint.lower()

    def test_both_filters_suggests_both(self):
        mixin = _make_mixin()
        form = _make_form(status="open", date_range="3months")
        hint = mixin.get_no_results_hint(form, result_count=0)
        # Should mention both hints joined with "and"
        assert " and " in hint

    def test_zero_results_always_returns_string(self):
        mixin = _make_mixin()
        form = _make_form()
        hint = mixin.get_no_results_hint(form, result_count=0)
        assert isinstance(hint, str)
        assert len(hint) > 0


class TestEnquiryFilterMixinDatesMatch:
    """Tests for EnquiryFilterMixin._dates_match_predefined_range."""

    def test_delegates_to_date_range_service(self):
        mixin = _make_mixin()
        with patch(
            "application.class_views.DateRangeService.dates_match_predefined_range",
            return_value=True,
        ) as mock:
            result = mixin._dates_match_predefined_range("2024-01-01", "2024-12-31")
            mock.assert_called_once_with("2024-01-01", "2024-12-31")
            assert result is True

    def test_returns_false_for_arbitrary_dates(self):
        mixin = _make_mixin()
        result = mixin._dates_match_predefined_range("2000-01-01", "2000-06-01")
        assert result is False


class TestEnquiryFilterMixinGetDefaultParams:
    """Tests for EnquiryFilterMixin.get_default_filter_params."""

    def test_returns_dict_with_status_and_date_range(self):
        mixin = _make_mixin()
        result = mixin.get_default_filter_params()
        assert isinstance(result, dict)
        assert "status" in result
        assert "date_range" in result


class TestFieldLookupsConstant:
    """Tests for EnquiryFilterMixin._FIELD_LOOKUPS."""

    def test_member_in_lookups(self):
        assert "member" in EnquiryFilterMixin._FIELD_LOOKUPS

    def test_ward_maps_to_member_ward(self):
        assert EnquiryFilterMixin._FIELD_LOOKUPS["ward"] == "member__ward"

    def test_section_in_lookups(self):
        assert "section" in EnquiryFilterMixin._FIELD_LOOKUPS


# ---------------------------------------------------------------------------
# Tests for _apply_status_filter
# ---------------------------------------------------------------------------
class TestApplyStatusFilter:
    """Tests for EnquiryFilterMixin._apply_status_filter."""

    def test_no_status_returns_queryset_unchanged(self):
        mixin = _make_mixin()
        qs = MagicMock()
        result = mixin._apply_status_filter(qs, {"status": ""})
        qs.filter.assert_not_called()
        assert result is qs

    def test_none_status_returns_queryset_unchanged(self):
        mixin = _make_mixin()
        qs = MagicMock()
        result = mixin._apply_status_filter(qs, {})
        qs.filter.assert_not_called()
        assert result is qs

    def test_open_status_filters_new_and_open(self):
        mixin = _make_mixin()
        qs = MagicMock()
        mixin._apply_status_filter(qs, {"status": "open"})
        qs.filter.assert_called_once_with(status__in=["new", "open"])

    def test_closed_status_filters_closed(self):
        mixin = _make_mixin()
        qs = MagicMock()
        mixin._apply_status_filter(qs, {"status": "closed"})
        qs.filter.assert_called_once_with(status="closed")

    def test_other_status_filters_exact(self):
        mixin = _make_mixin()
        qs = MagicMock()
        mixin._apply_status_filter(qs, {"status": "new"})
        qs.filter.assert_called_once_with(status="new")


# ---------------------------------------------------------------------------
# Tests for _apply_field_filters
# ---------------------------------------------------------------------------
class TestApplyFieldFilters:
    """Tests for EnquiryFilterMixin._apply_field_filters."""

    def test_empty_cleaned_data_returns_queryset_unchanged(self):
        mixin = _make_mixin()
        qs = MagicMock()
        result = mixin._apply_field_filters(qs, {})
        qs.filter.assert_not_called()
        assert result is qs

    def test_member_value_applies_filter(self):
        mixin = _make_mixin()
        qs = MagicMock()
        # Each filter call returns a new mock to chain
        qs.filter.return_value = qs
        member_val = MagicMock()
        mixin._apply_field_filters(qs, {"member": member_val})
        qs.filter.assert_any_call(member=member_val)

    def test_ward_value_applies_member_ward_lookup(self):
        mixin = _make_mixin()
        qs = MagicMock()
        qs.filter.return_value = qs
        ward_val = MagicMock()
        mixin._apply_field_filters(qs, {"ward": ward_val})
        qs.filter.assert_any_call(member__ward=ward_val)

    def test_multiple_fields_all_applied(self):
        mixin = _make_mixin()
        qs = MagicMock()
        qs.filter.return_value = qs
        member_val = MagicMock()
        section_val = MagicMock()
        mixin._apply_field_filters(qs, {"member": member_val, "section": section_val})
        qs.filter.assert_any_call(member=member_val)
        qs.filter.assert_any_call(section=section_val)
        assert qs.filter.call_count == 2

    def test_none_values_are_skipped(self):
        mixin = _make_mixin()
        qs = MagicMock()
        mixin._apply_field_filters(qs, {"member": None, "admin": None, "section": None})
        qs.filter.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for _apply_overdue_filter
# ---------------------------------------------------------------------------
class TestApplyOverdueFilter:
    """Tests for EnquiryFilterMixin._apply_overdue_filter."""

    def test_overdue_only_false_returns_queryset_unchanged(self):
        mixin = _make_mixin()
        qs = MagicMock()
        result = mixin._apply_overdue_filter(qs, {"overdue_only": False})
        qs.filter.assert_not_called()
        assert result is qs

    def test_overdue_only_missing_returns_queryset_unchanged(self):
        mixin = _make_mixin()
        qs = MagicMock()
        result = mixin._apply_overdue_filter(qs, {})
        qs.filter.assert_not_called()
        assert result is qs

    def test_overdue_only_true_applies_filter(self):
        mixin = _make_mixin()
        qs = MagicMock()
        with patch("application.class_views.timezone") as mock_tz:
            from datetime import timedelta

            fake_now = MagicMock()
            mock_tz.now.return_value = fake_now
            expected_date = fake_now - timedelta(days=5)

            mixin._apply_overdue_filter(qs, {"overdue_only": True})

            qs.filter.assert_called_once_with(
                status__in=["new", "open"], created_at__lt=expected_date
            )


# ---------------------------------------------------------------------------
# Tests for _apply_search_filter
# ---------------------------------------------------------------------------
class TestApplySearchFilter:
    """Tests for EnquiryFilterMixin._apply_search_filter."""

    def test_no_search_term_returns_queryset_unchanged(self):
        mixin = _make_mixin()
        qs = MagicMock()
        result = mixin._apply_search_filter(qs, {"search": ""})
        assert result is qs

    def test_missing_search_key_returns_queryset_unchanged(self):
        mixin = _make_mixin()
        qs = MagicMock()
        result = mixin._apply_search_filter(qs, {})
        assert result is qs

    @patch("application.class_views.EnquirySearchService.apply_search")
    def test_search_with_narrowing_filters_no_limit(self, mock_apply):
        mixin = _make_mixin()
        qs = MagicMock()
        searched_qs = MagicMock()
        mock_apply.return_value = searched_qs

        result = mixin._apply_search_filter(
            qs,
            {
                "search": "test query",
                "status": "open",
                "date_range": "all",
                "member": None,
                "admin": None,
                "section": None,
            },
        )
        mock_apply.assert_called_once_with(qs, "test query")
        # No slicing should occur -- result is the searched queryset itself
        searched_qs.__getitem__.assert_not_called()
        assert result is searched_qs

    @patch("application.class_views.EnquirySearchService.apply_search")
    def test_search_without_narrowing_filters_applies_limit(self, mock_apply):
        mixin = _make_mixin()
        qs = MagicMock()
        searched_qs = MagicMock()
        sliced_qs = MagicMock()
        mock_apply.return_value = searched_qs
        searched_qs.__getitem__ = MagicMock(return_value=sliced_qs)

        result = mixin._apply_search_filter(
            qs,
            {
                "search": "test query",
                "status": "all",
                "date_range": "all",
                "member": None,
                "admin": None,
                "section": None,
            },
        )
        mock_apply.assert_called_once_with(qs, "test query")
        searched_qs.__getitem__.assert_called_once_with(slice(None, 500))
        assert result is sliced_qs

    @patch("application.class_views.EnquirySearchService.apply_search")
    def test_search_with_member_counts_as_narrowing(self, mock_apply):
        mixin = _make_mixin()
        qs = MagicMock()
        searched_qs = MagicMock()
        mock_apply.return_value = searched_qs

        result = mixin._apply_search_filter(
            qs,
            {
                "search": "query",
                "status": "all",
                "date_range": "all",
                "member": MagicMock(),  # non-falsy
                "admin": None,
                "section": None,
            },
        )
        searched_qs.__getitem__.assert_not_called()
        assert result is searched_qs


# ---------------------------------------------------------------------------
# Tests for EnquiryCloseView._build_resolution_time_data
# ---------------------------------------------------------------------------
class TestBuildResolutionTimeData:
    """Tests for EnquiryCloseView._build_resolution_time_data."""

    def _make_view(self):
        from application.class_views import EnquiryCloseView

        return EnquiryCloseView()

    def test_closed_at_none_returns_none_values(self):
        view = self._make_view()
        enquiry = MagicMock()
        enquiry.closed_at = None

        result = view._build_resolution_time_data(enquiry)

        assert result["business_days"] is None
        assert result["calendar_days"] is None
        assert result["display"] == "-"
        assert result["color_class"] == ""

    @patch("application.class_views.resolution_time_color", create=True)
    @patch("application.class_views.calculate_calendar_days", create=True)
    @patch("application.class_views.calculate_business_days", create=True)
    def test_closed_at_set_returns_proper_data(self, mock_biz, mock_cal, mock_color):
        # The imports are inside the method, so we patch at the utils level
        with patch(
            "application.utils.calculate_business_days", return_value=3
        ) as mock_biz_days, patch(
            "application.utils.calculate_calendar_days", return_value=5
        ) as mock_cal_days, patch(
            "application.templatetags.list_extras.resolution_time_color",
            return_value="text-success",
        ) as mock_rtc:
            view = self._make_view()
            enquiry = MagicMock()
            enquiry.closed_at = MagicMock()  # truthy
            enquiry.created_at = MagicMock()

            result = view._build_resolution_time_data(enquiry)

            mock_biz_days.assert_called_once_with(enquiry.created_at, enquiry.closed_at)
            mock_cal_days.assert_called_once_with(enquiry.created_at, enquiry.closed_at)
            mock_rtc.assert_called_once_with(3)
            assert result["business_days"] == 3
            assert result["calendar_days"] == 5
            assert result["display"] == "3"
            assert result["color_class"] == "text-success"


# ---------------------------------------------------------------------------
# Tests for EnquiryCloseView._handle_ajax_close
# ---------------------------------------------------------------------------
class TestHandleAjaxClose:
    """Tests for EnquiryCloseView._handle_ajax_close."""

    def _make_view(self):
        from application.class_views import EnquiryCloseView

        return EnquiryCloseView()

    def test_empty_service_type_returns_error(self):
        import json

        view = self._make_view()
        request = MagicMock()
        enquiry = MagicMock()

        response = view._handle_ajax_close(request, enquiry, "")
        data = json.loads(response.content)

        assert data["success"] is False
        assert "Service type is required" in data["message"]

    @patch("application.class_views.EnquiryService.close_enquiry")
    def test_value_error_returns_error_message(self, mock_close):
        import json

        mock_close.side_effect = ValueError("Invalid service type")
        view = self._make_view()
        request = MagicMock()
        enquiry = MagicMock()

        response = view._handle_ajax_close(request, enquiry, "some_type")
        data = json.loads(response.content)

        assert data["success"] is False
        assert data["message"] == "Invalid service type"

    @patch("application.class_views.EnquiryService.close_enquiry")
    def test_already_closed_returns_error(self, mock_close):
        import json

        mock_close.return_value = False
        view = self._make_view()
        request = MagicMock()
        enquiry = MagicMock()
        enquiry.reference = "ENQ-001"

        response = view._handle_ajax_close(request, enquiry, "some_type")
        data = json.loads(response.content)

        assert data["success"] is False
        assert "already closed" in data["message"]

    @patch("application.class_views.EnquiryService.close_enquiry")
    def test_successful_close_returns_success(self, mock_close):
        import json

        mock_close.return_value = True
        view = self._make_view()
        request = MagicMock()
        enquiry = MagicMock()
        enquiry.reference = "ENQ-001"
        enquiry.id = 42
        enquiry.status = "closed"
        enquiry.get_status_display.return_value = "Closed"
        enquiry.closed_at = None  # simplify _build_resolution_time_data
        enquiry.service_type = "some_type"
        enquiry.get_service_type_display.return_value = "Some Type"

        response = view._handle_ajax_close(request, enquiry, "some_type")
        data = json.loads(response.content)

        assert data["success"] is True
        assert "ENQ-001" in data["message"]


# ---------------------------------------------------------------------------
# Tests for EnquiryCloseView._handle_standard_close
# ---------------------------------------------------------------------------
class TestHandleStandardClose:
    """Tests for EnquiryCloseView._handle_standard_close."""

    def _make_view(self):
        from application.class_views import EnquiryCloseView

        return EnquiryCloseView()

    @patch("application.class_views.redirect")
    @patch("application.class_views.messages")
    def test_empty_service_type_shows_error_and_redirects(
        self, mock_messages, mock_redirect
    ):
        view = self._make_view()
        request = MagicMock()
        enquiry = MagicMock()

        view._handle_standard_close(request, enquiry, pk=1, service_type="")

        mock_messages.error.assert_called_once_with(
            request, "Service type is required to close an enquiry."
        )
        mock_redirect.assert_called_with("application:enquiry_detail", pk=1)

    @patch("application.class_views.EnquiryService.close_enquiry")
    @patch("application.class_views.redirect")
    @patch("application.class_views.messages")
    def test_successful_close_shows_success(
        self, mock_messages, mock_redirect, mock_close
    ):
        mock_close.return_value = True
        view = self._make_view()
        request = MagicMock()
        request.META = {}
        enquiry = MagicMock()
        enquiry.reference = "ENQ-002"

        view._handle_standard_close(request, enquiry, pk=2, service_type="type_a")

        mock_messages.success.assert_called_once()
        assert "ENQ-002" in mock_messages.success.call_args[0][1]

    @patch("application.class_views.EnquiryService.close_enquiry")
    @patch("application.class_views.redirect")
    @patch("application.class_views.messages")
    def test_already_closed_shows_warning(
        self, mock_messages, mock_redirect, mock_close
    ):
        mock_close.return_value = False
        view = self._make_view()
        request = MagicMock()
        request.META = {}
        enquiry = MagicMock()
        enquiry.reference = "ENQ-003"

        view._handle_standard_close(request, enquiry, pk=3, service_type="type_a")

        mock_messages.warning.assert_called_once()
        assert "already closed" in mock_messages.warning.call_args[0][1]

    @patch("application.class_views.EnquiryService.close_enquiry")
    @patch("application.class_views.redirect")
    @patch("application.class_views.messages")
    def test_value_error_shows_error(self, mock_messages, mock_redirect, mock_close):
        mock_close.side_effect = ValueError("Bad value")
        view = self._make_view()
        request = MagicMock()
        enquiry = MagicMock()

        view._handle_standard_close(request, enquiry, pk=4, service_type="type_a")

        mock_messages.error.assert_called_once_with(request, "Bad value")
        mock_redirect.assert_called_with("application:enquiry_detail", pk=4)


# ---------------------------------------------------------------------------
# Tests for EnquiryCloseView._resolve_redirect
# ---------------------------------------------------------------------------
class TestResolveRedirect:
    """Tests for EnquiryCloseView._resolve_redirect."""

    def _make_view(self):
        from application.class_views import EnquiryCloseView

        return EnquiryCloseView()

    @patch("application.class_views.redirect")
    def test_referer_is_detail_page_redirects_to_detail(self, mock_redirect):
        view = self._make_view()
        request = MagicMock()
        request.META = {"HTTP_REFERER": "http://example.com/enquiries/10/"}
        enquiry = MagicMock()
        enquiry.pk = 10

        view._resolve_redirect(request, pk=10, enquiry=enquiry)

        mock_redirect.assert_called_with("application:enquiry_detail", pk=10)

    @patch("application.class_views.HttpResponseRedirect")
    def test_referer_is_enquiries_list_redirects_to_referer(self, mock_http_redirect):
        view = self._make_view()
        request = MagicMock()
        referer = "http://example.com/enquiries/?status=open"
        request.META = {"HTTP_REFERER": referer}
        enquiry = MagicMock()
        enquiry.pk = 10

        view._resolve_redirect(request, pk=10, enquiry=enquiry)

        mock_http_redirect.assert_called_with(referer)

    @patch("application.class_views.HttpResponseRedirect")
    def test_referer_is_home_page_redirects_to_referer(self, mock_http_redirect):
        view = self._make_view()
        request = MagicMock()
        referer = "http://example.com/home/"
        request.META = {"HTTP_REFERER": referer}
        enquiry = MagicMock()
        enquiry.pk = 10

        view._resolve_redirect(request, pk=10, enquiry=enquiry)

        mock_http_redirect.assert_called_with(referer)

    @patch("application.class_views.redirect")
    def test_referer_is_edit_page_does_not_redirect_to_detail(self, mock_redirect):
        view = self._make_view()
        request = MagicMock()
        request.META = {"HTTP_REFERER": "http://example.com/enquiries/10/edit"}
        enquiry = MagicMock()
        enquiry.pk = 10

        view._resolve_redirect(request, pk=10, enquiry=enquiry)

        # Should NOT redirect to detail (the /edit check), should match
        # the second condition "/enquiries/" and use HttpResponseRedirect
        # Actually, the /edit referer contains /enquiries/10/ AND /edit,
        # so the first if is False (edit in referer).
        # Then "/enquiries/" in referer is True, so HttpResponseRedirect.
        # redirect should NOT be called with enquiry_detail
        for call in mock_redirect.call_args_list:
            assert call != (("application:enquiry_detail",), {"pk": 10})

    @patch("application.class_views.redirect")
    def test_no_referer_redirects_to_list(self, mock_redirect):
        view = self._make_view()
        request = MagicMock()
        request.META = {}
        enquiry = MagicMock()

        view._resolve_redirect(request, pk=10, enquiry=enquiry)

        mock_redirect.assert_called_with("application:enquiry_list")
