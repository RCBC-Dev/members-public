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
Tests for pure-logic helper methods in application/export_views.py
"""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from application.export_views import ExportDataProcessor


class TestExtractDate:
    """Tests for ExportDataProcessor._extract_date."""

    def test_date_object_returned_as_is(self):
        d = date(2024, 6, 15)
        result = ExportDataProcessor._extract_date(d)
        assert result == d

    def test_datetime_extracted_to_date(self):
        dt = datetime(2024, 6, 15, 10, 30)
        result = ExportDataProcessor._extract_date(dt)
        assert result == date(2024, 6, 15)


class TestFormatDate:
    """Tests for ExportDataProcessor._format_date."""

    def test_formats_to_uk_date(self):
        d = date(2024, 6, 15)
        result = ExportDataProcessor._format_date(d)
        assert result == "15/06/2024"

    def test_pads_single_digit_day_and_month(self):
        d = date(2024, 3, 5)
        result = ExportDataProcessor._format_date(d)
        assert result == "05/03/2024"


class TestCalculateOverdueDays:
    """Tests for ExportDataProcessor._calculate_overdue_days."""

    def test_closed_enquiry_returns_dash(self):
        today = date(2024, 6, 15)
        result = ExportDataProcessor._calculate_overdue_days(
            due_date=date(2024, 6, 10),
            today=today,
            status="closed",
        )
        assert result == "-"

    def test_future_due_date_returns_dash(self):
        today = date(2024, 6, 15)
        result = ExportDataProcessor._calculate_overdue_days(
            due_date=date(2024, 6, 20),
            today=today,
            status="open",
        )
        assert result == "-"

    def test_past_due_date_returns_business_days(self):
        today = date(2024, 6, 17)  # Monday
        result = ExportDataProcessor._calculate_overdue_days(
            due_date=date(2024, 6, 12),  # Previous Wednesday
            today=today,
            status="open",
        )
        # Should return a number as string
        assert result != "-"
        assert result.isdigit() or result == "-"

    def test_due_today_returns_dash(self):
        today = date(2024, 6, 15)
        result = ExportDataProcessor._calculate_overdue_days(
            due_date=today,
            today=today,
            status="open",
        )
        assert result == "-"


class TestCalculateResolutionTime:
    """Tests for ExportDataProcessor._calculate_resolution_time."""

    def test_open_enquiry_returns_dash(self):
        enquiry = MagicMock()
        enquiry.status = "open"
        result = ExportDataProcessor._calculate_resolution_time(enquiry)
        assert result == "-"

    def test_closed_without_closed_at_returns_dash(self):
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = None
        result = ExportDataProcessor._calculate_resolution_time(enquiry)
        assert result == "-"

    def test_new_status_returns_dash(self):
        enquiry = MagicMock()
        enquiry.status = "new"
        result = ExportDataProcessor._calculate_resolution_time(enquiry)
        assert result == "-"

    def test_closed_with_dates_returns_string(self):
        from django.utils import timezone

        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.created_at = timezone.make_aware(datetime(2024, 6, 10))
        enquiry.closed_at = timezone.make_aware(datetime(2024, 6, 17))
        result = ExportDataProcessor._calculate_resolution_time(enquiry)
        assert result != "-"
        # Should be a number as string
        try:
            int(result)
        except ValueError:
            pytest.fail(f"Expected numeric string, got: {result}")


class TestGetAdminDisplay:
    """Tests for ExportDataProcessor._get_admin_display."""

    def test_no_admin_returns_unassigned(self):
        enquiry = MagicMock()
        enquiry.admin = None
        result = ExportDataProcessor._get_admin_display(enquiry)
        assert result == "Unassigned"

    def test_admin_without_user_returns_unassigned(self):
        enquiry = MagicMock()
        enquiry.admin = MagicMock()
        enquiry.admin.user = None
        result = ExportDataProcessor._get_admin_display(enquiry)
        assert result == "Unassigned"

    def test_admin_with_full_name(self):
        enquiry = MagicMock()
        enquiry.admin = MagicMock()
        enquiry.admin.user = MagicMock()
        enquiry.admin.user.get_full_name.return_value = "John Smith"
        enquiry.admin.user.username = "jsmith"
        result = ExportDataProcessor._get_admin_display(enquiry)
        assert result == "John Smith"

    def test_admin_without_full_name_uses_username(self):
        enquiry = MagicMock()
        enquiry.admin = MagicMock()
        enquiry.admin.user = MagicMock()
        enquiry.admin.user.get_full_name.return_value = ""
        enquiry.admin.user.username = "jsmith"
        result = ExportDataProcessor._get_admin_display(enquiry)
        assert result == "jsmith"


class TestNotAssignedConstant:
    """Test the NOT_ASSIGNED constant."""

    def test_not_assigned_value(self):
        assert ExportDataProcessor.NOT_ASSIGNED == "Not assigned"


class TestFieldLookupsConstant:
    """Tests for ExportDataProcessor._FIELD_LOOKUPS."""

    def test_member_in_lookups(self):
        assert "member" in ExportDataProcessor._FIELD_LOOKUPS

    def test_ward_maps_to_member_ward(self):
        assert ExportDataProcessor._FIELD_LOOKUPS["ward"] == "member__ward"

    def test_section_in_lookups(self):
        assert "section" in ExportDataProcessor._FIELD_LOOKUPS


# ---------------------------------------------------------------------------
# Tests for _build_enquiry_row
# ---------------------------------------------------------------------------


class TestBuildEnquiryRow:
    """Tests for ExportDataProcessor._build_enquiry_row."""

    @staticmethod
    def _make_enquiry(**overrides):
        """Create a MagicMock enquiry with sensible defaults."""
        from django.utils import timezone as tz

        enquiry = MagicMock()
        enquiry.reference = overrides.get("reference", "ENQ-001")
        enquiry.title = overrides.get("title", "Test Enquiry")
        enquiry.status = overrides.get("status", "open")
        enquiry.get_status_display.return_value = overrides.get(
            "status_display", "Open"
        )

        # Member
        enquiry.member = MagicMock()
        enquiry.member.full_name = overrides.get("member_name", "Jane Doe")

        # FK fields -- section, job_type, contact
        if overrides.get("section_none", False):
            enquiry.section = None
        else:
            enquiry.section = MagicMock()
            enquiry.section.name = overrides.get("section_name", "Highways")

        if overrides.get("job_type_none", False):
            enquiry.job_type = None
        else:
            enquiry.job_type = MagicMock()
            enquiry.job_type.name = overrides.get("job_type_name", "Pothole")

        if overrides.get("contact_none", False):
            enquiry.contact = None
        else:
            enquiry.contact = MagicMock()
            enquiry.contact.name = overrides.get("contact_name", "Bob Smith")

        # Dates
        base_dt = tz.make_aware(datetime(2024, 6, 10, 9, 0))
        enquiry.created_at = overrides.get("created_at", base_dt)
        enquiry.updated_at = overrides.get(
            "updated_at", tz.make_aware(datetime(2024, 6, 12, 14, 30))
        )
        enquiry.due_date = overrides.get("due_date", date(2024, 6, 20))
        enquiry.closed_at = overrides.get("closed_at", None)

        # Admin
        enquiry.admin = MagicMock()
        enquiry.admin.user = MagicMock()
        enquiry.admin.user.get_full_name.return_value = overrides.get(
            "admin_full_name", "Admin User"
        )
        enquiry.admin.user.username = overrides.get("admin_username", "adminuser")

        return enquiry

    def test_all_fk_fields_present(self):
        """When section, job_type, contact are set their .name values appear."""
        enquiry = self._make_enquiry()
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))

        assert row["section"] == "Highways"
        assert row["job_type"] == "Pothole"
        assert row["contact"] == "Bob Smith"

    def test_section_none_gives_not_assigned(self):
        enquiry = self._make_enquiry(section_none=True)
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["section"] == "Not assigned"

    def test_job_type_none_gives_not_assigned(self):
        enquiry = self._make_enquiry(job_type_none=True)
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["job_type"] == "Not assigned"

    def test_contact_none_gives_not_assigned(self):
        enquiry = self._make_enquiry(contact_none=True)
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["contact"] == "Not assigned"

    def test_status_new_shows_open(self):
        """When enquiry.status is 'new' the row status should be 'Open'."""
        enquiry = self._make_enquiry(status="new", status_display="New")
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["status"] == "Open"

    def test_status_open_uses_get_status_display(self):
        """When status is 'open', we rely on get_status_display()."""
        enquiry = self._make_enquiry(status="open", status_display="Open")
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["status"] == "Open"
        enquiry.get_status_display.assert_called()

    def test_closed_with_closed_at_has_formatted_date(self):
        from django.utils import timezone as tz

        closed_dt = tz.make_aware(datetime(2024, 6, 18, 16, 0))
        enquiry = self._make_enquiry(
            status="closed", status_display="Closed", closed_at=closed_dt
        )
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 20))
        assert row["closed"] == "18/06/2024"

    def test_closed_without_closed_at_gives_dash(self):
        enquiry = self._make_enquiry(
            status="closed", status_display="Closed", closed_at=None
        )
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 20))
        assert row["closed"] == "-"

    def test_reference_none_gives_no_ref(self):
        enquiry = self._make_enquiry(reference=None)
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["reference"] == "No Ref"

    def test_reference_present_is_used(self):
        enquiry = self._make_enquiry(reference="ENQ-999")
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["reference"] == "ENQ-999"

    def test_row_contains_all_expected_keys(self):
        """The returned dict should contain every expected export column."""
        enquiry = self._make_enquiry()
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        expected_keys = {
            "reference",
            "title",
            "member",
            "section",
            "job_type",
            "contact",
            "status",
            "admin",
            "created",
            "updated",
            "due_date",
            "overdue_days",
            "closed",
            "resolution_time",
        }
        assert set(row.keys()) == expected_keys

    def test_created_and_updated_dates_formatted(self):
        from django.utils import timezone as tz

        enquiry = self._make_enquiry(
            created_at=tz.make_aware(datetime(2024, 3, 5, 8, 0)),
            updated_at=tz.make_aware(datetime(2024, 4, 10, 12, 0)),
        )
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["created"] == "05/03/2024"
        assert row["updated"] == "10/04/2024"

    def test_member_full_name_in_row(self):
        enquiry = self._make_enquiry(member_name="Alice Wonderland")
        row = ExportDataProcessor._build_enquiry_row(enquiry, date(2024, 6, 15))
        assert row["member"] == "Alice Wonderland"


# ---------------------------------------------------------------------------
# Tests for _apply_status_filter
# ---------------------------------------------------------------------------


class TestApplyStatusFilter:
    """Tests for ExportDataProcessor._apply_status_filter."""

    def test_no_status_returns_queryset_unchanged(self):
        queryset = MagicMock()
        form = MagicMock()
        form.cleaned_data = {}
        result = ExportDataProcessor._apply_status_filter(queryset, form)
        assert result is queryset
        queryset.filter.assert_not_called()

    def test_empty_string_status_returns_queryset_unchanged(self):
        queryset = MagicMock()
        form = MagicMock()
        form.cleaned_data = {"status": ""}
        result = ExportDataProcessor._apply_status_filter(queryset, form)
        assert result is queryset
        queryset.filter.assert_not_called()

    def test_none_status_returns_queryset_unchanged(self):
        queryset = MagicMock()
        form = MagicMock()
        form.cleaned_data = {"status": None}
        result = ExportDataProcessor._apply_status_filter(queryset, form)
        assert result is queryset
        queryset.filter.assert_not_called()

    def test_open_status_filters_new_and_open(self):
        queryset = MagicMock()
        form = MagicMock()
        form.cleaned_data = {"status": "open"}
        ExportDataProcessor._apply_status_filter(queryset, form)
        queryset.filter.assert_called_once_with(status__in=["new", "open"])

    def test_closed_status_filters_closed(self):
        queryset = MagicMock()
        form = MagicMock()
        form.cleaned_data = {"status": "closed"}
        ExportDataProcessor._apply_status_filter(queryset, form)
        queryset.filter.assert_called_once_with(status="closed")

    def test_returns_filtered_queryset(self):
        queryset = MagicMock()
        filtered_qs = MagicMock()
        queryset.filter.return_value = filtered_qs
        form = MagicMock()
        form.cleaned_data = {"status": "closed"}
        result = ExportDataProcessor._apply_status_filter(queryset, form)
        assert result is filtered_qs


# ---------------------------------------------------------------------------
# Tests for _apply_field_filters
# ---------------------------------------------------------------------------


class TestApplyFieldFilters:
    """Tests for ExportDataProcessor._apply_field_filters."""

    def test_no_fields_set_returns_queryset_unchanged(self):
        queryset = MagicMock()
        form = MagicMock()
        form.cleaned_data = {
            "member": None,
            "admin": None,
            "section": None,
            "job_type": None,
            "contact": None,
            "ward": None,
        }
        result = ExportDataProcessor._apply_field_filters(queryset, form)
        assert result is queryset
        queryset.filter.assert_not_called()

    def test_empty_cleaned_data_returns_queryset_unchanged(self):
        queryset = MagicMock()
        form = MagicMock()
        form.cleaned_data = {}
        result = ExportDataProcessor._apply_field_filters(queryset, form)
        assert result is queryset
        queryset.filter.assert_not_called()

    def test_member_field_set_filters_by_member(self):
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        member_value = MagicMock()
        form = MagicMock()
        form.cleaned_data = {"member": member_value}
        ExportDataProcessor._apply_field_filters(queryset, form)
        queryset.filter.assert_any_call(member=member_value)

    def test_ward_field_set_filters_by_member_ward(self):
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        ward_value = MagicMock()
        form = MagicMock()
        form.cleaned_data = {"ward": ward_value}
        ExportDataProcessor._apply_field_filters(queryset, form)
        queryset.filter.assert_any_call(member__ward=ward_value)

    def test_section_field_set_filters_by_section(self):
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        section_value = MagicMock()
        form = MagicMock()
        form.cleaned_data = {"section": section_value}
        ExportDataProcessor._apply_field_filters(queryset, form)
        queryset.filter.assert_any_call(section=section_value)

    def test_multiple_fields_all_applied(self):
        """When multiple fields are set, filter is called for each."""
        queryset = MagicMock()
        queryset.filter.return_value = queryset

        member_val = MagicMock()
        section_val = MagicMock()
        ward_val = MagicMock()
        form = MagicMock()
        form.cleaned_data = {
            "member": member_val,
            "section": section_val,
            "ward": ward_val,
        }
        ExportDataProcessor._apply_field_filters(queryset, form)

        queryset.filter.assert_any_call(member=member_val)
        queryset.filter.assert_any_call(section=section_val)
        queryset.filter.assert_any_call(member__ward=ward_val)
        assert queryset.filter.call_count == 3

    def test_returns_final_filtered_queryset(self):
        """Each successive .filter() call chains; final result is returned."""
        qs1 = MagicMock()
        qs2 = MagicMock()
        qs1.filter.return_value = qs2
        qs2.filter.return_value = qs2  # further calls return same

        form = MagicMock()
        form.cleaned_data = {"member": MagicMock(), "section": MagicMock()}
        result = ExportDataProcessor._apply_field_filters(qs1, form)
        assert result is qs2


# ---------------------------------------------------------------------------
# Tests for _apply_search
# ---------------------------------------------------------------------------


class TestApplySearch:
    """Tests for ExportDataProcessor._apply_search."""

    @patch("application.export_views.EnquirySearchService")
    def test_delegates_to_search_service(self, mock_search_cls):
        """_apply_search should call EnquirySearchService.apply_search."""
        queryset = MagicMock()
        filtered_qs = MagicMock()
        mock_search_cls.apply_search.return_value = filtered_qs

        processor = ExportDataProcessor.__new__(ExportDataProcessor)
        result = processor._apply_search(queryset, "pothole")

        mock_search_cls.apply_search.assert_called_once_with(queryset, "pothole")
        assert result is filtered_qs

    @patch("application.export_views.EnquirySearchService")
    def test_passes_search_value_exactly(self, mock_search_cls):
        """The search value should be forwarded without modification."""
        queryset = MagicMock()
        mock_search_cls.apply_search.return_value = queryset

        processor = ExportDataProcessor.__new__(ExportDataProcessor)
        processor._apply_search(queryset, "  some search  ")

        mock_search_cls.apply_search.assert_called_once_with(
            queryset, "  some search  "
        )
