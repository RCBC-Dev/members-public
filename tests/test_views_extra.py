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
Tests for helper functions in application/views.py not covered by test_views_helpers.py.
Focuses on date/filter helpers, SLA classification, and business day stats.
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from django.db.models import Q
from django.utils import timezone

from application.views import (
    _apply_date_and_member_filters,
    _calculate_business_days_stats,
    _group_by_member,
    _build_date_filter_q,
    _build_status_filters,
    _classify_enquiry_for_sla,
    _filter_active_sections,
)


class TestApplyDateAndMemberFilters:
    """Tests for _apply_date_and_member_filters."""

    def test_no_filters_returns_queryset(self):
        qs = MagicMock()
        result = _apply_date_and_member_filters(qs, None, None, None, None)
        assert result is qs
        qs.filter.assert_not_called()

    def test_date_from_only(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        d = date(2026, 1, 1)
        _apply_date_and_member_filters(qs, d, None, None, None)
        qs.filter.assert_called_once_with(created_at__gte=d)

    def test_date_to_only(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        d = date(2026, 6, 30)
        _apply_date_and_member_filters(qs, None, d, None, None)
        qs.filter.assert_called_once_with(created_at__lte=d)

    def test_both_dates(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        d1 = date(2026, 1, 1)
        d2 = date(2026, 6, 30)
        _apply_date_and_member_filters(qs, d1, d2, None, None)
        assert qs.filter.call_count == 2

    def test_member_id(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        _apply_date_and_member_filters(qs, None, None, 42, None)
        qs.filter.assert_called_once_with(member_id=42)

    def test_service_type(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        _apply_date_and_member_filters(qs, None, None, None, "new_addition")
        qs.filter.assert_called_once_with(service_type="new_addition")

    def test_all_filters(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        d1 = date(2026, 1, 1)
        d2 = date(2026, 6, 30)
        _apply_date_and_member_filters(qs, d1, d2, 5, "failed_service")
        assert qs.filter.call_count == 4


class TestCalculateBusinessDaysStats:
    """Tests for _calculate_business_days_stats."""

    def test_empty_queryset(self):
        enquiry_list, total, count, avg = _calculate_business_days_stats([])
        assert enquiry_list == []
        assert total == 0
        assert count == 0
        assert avg == 0

    def test_enquiry_without_dates_skipped(self):
        e = MagicMock()
        e.created_at = None
        e.closed_at = None
        enquiry_list, total, count, avg = _calculate_business_days_stats([e])
        assert count == 0

    def test_enquiry_with_missing_closed_at_skipped(self):
        e = MagicMock()
        e.created_at = timezone.now()
        e.closed_at = None
        enquiry_list, total, count, avg = _calculate_business_days_stats([e])
        assert count == 0

    @patch("application.utils.calculate_business_days", return_value=5)
    def test_valid_enquiry(self, mock_calc):
        e = MagicMock()
        e.created_at = timezone.now() - timedelta(days=7)
        e.closed_at = timezone.now()

        enquiry_list, total, count, avg = _calculate_business_days_stats([e])
        assert count == 1
        assert total == 5
        assert avg == 5.0
        assert len(enquiry_list) == 1
        assert enquiry_list[0]["business_days"] == 5

    @patch("application.utils.calculate_business_days", return_value=None)
    def test_none_business_days_skipped(self, mock_calc):
        e = MagicMock()
        e.created_at = timezone.now() - timedelta(days=7)
        e.closed_at = timezone.now()

        enquiry_list, total, count, avg = _calculate_business_days_stats([e])
        assert count == 0

    @patch("application.utils.calculate_business_days")
    def test_multiple_enquiries(self, mock_calc):
        mock_calc.side_effect = [3, 7]
        e1 = MagicMock()
        e1.created_at = timezone.now() - timedelta(days=5)
        e1.closed_at = timezone.now()
        e2 = MagicMock()
        e2.created_at = timezone.now() - timedelta(days=10)
        e2.closed_at = timezone.now()

        enquiry_list, total, count, avg = _calculate_business_days_stats([e1, e2])
        assert count == 2
        assert total == 10
        assert avg == 5.0


class TestGroupByMember:
    """Tests for _group_by_member."""

    def test_empty_list(self):
        result = _group_by_member([])
        assert result == {}

    def test_single_enquiry(self):
        member = MagicMock()
        member.id = 1
        enquiry = MagicMock()
        enquiry.member = member

        items = [{"enquiry": enquiry, "business_days": 5}]
        result = _group_by_member(items)

        assert 1 in result
        assert result[1]["total_enquiries"] == 1
        assert result[1]["total_days"] == 5
        assert result[1]["avg_days"] == 5.0

    def test_multiple_enquiries_same_member(self):
        member = MagicMock()
        member.id = 1
        e1 = MagicMock()
        e1.member = member
        e2 = MagicMock()
        e2.member = member

        items = [
            {"enquiry": e1, "business_days": 3},
            {"enquiry": e2, "business_days": 7},
        ]
        result = _group_by_member(items)

        assert result[1]["total_enquiries"] == 2
        assert result[1]["total_days"] == 10
        assert result[1]["avg_days"] == 5.0

    def test_multiple_members(self):
        m1 = MagicMock()
        m1.id = 1
        m2 = MagicMock()
        m2.id = 2
        e1 = MagicMock()
        e1.member = m1
        e2 = MagicMock()
        e2.member = m2

        items = [
            {"enquiry": e1, "business_days": 3},
            {"enquiry": e2, "business_days": 7},
        ]
        result = _group_by_member(items)

        assert len(result) == 2
        assert result[1]["avg_days"] == 3.0
        assert result[2]["avg_days"] == 7.0


class TestBuildDateFilterQ:
    """Tests for _build_date_filter_q."""

    def test_no_filters_returns_empty_q(self):
        result = _build_date_filter_q(None, None, None)
        assert isinstance(result, Q)

    def test_date_from(self):
        d = date(2026, 1, 1)
        result = _build_date_filter_q(d, None, None)
        assert isinstance(result, Q)

    def test_date_to(self):
        d = date(2026, 6, 30)
        result = _build_date_filter_q(None, d, None)
        assert isinstance(result, Q)

    def test_service_type(self):
        result = _build_date_filter_q(None, None, "new_addition")
        assert isinstance(result, Q)

    def test_custom_prefix(self):
        d = date(2026, 1, 1)
        result = _build_date_filter_q(d, None, None, prefix="my_prefix")
        assert isinstance(result, Q)


class TestBuildStatusFilters:
    """Tests for _build_status_filters."""

    def test_returns_two_q_objects(self):
        open_f, closed_f = _build_status_filters(Q())
        assert isinstance(open_f, Q)
        assert isinstance(closed_f, Q)

    def test_with_base_filter(self):
        base = Q(enquiries__created_at__gte=date(2026, 1, 1))
        open_f, closed_f = _build_status_filters(base)
        assert isinstance(open_f, Q)
        assert isinstance(closed_f, Q)

    def test_custom_prefix(self):
        open_f, closed_f = _build_status_filters(Q(), prefix="jobs")
        assert isinstance(open_f, Q)
        assert isinstance(closed_f, Q)


class TestClassifyEnquiryForSla:
    """Tests for _classify_enquiry_for_sla."""

    @patch("application.views.settings")
    @patch("application.utils.calculate_business_days", return_value=3)
    def test_closed_within_sla(self, mock_calc, mock_settings):
        mock_settings.ENQUIRY_SLA_DAYS = 5
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = timezone.now()
        enquiry.created_at = timezone.now() - timedelta(days=4)

        section_data = {}
        section = MagicMock()
        _classify_enquiry_for_sla(enquiry, section_data, 1, "Test Section", section)

        assert section_data[1]["enquiries_within_sla"] == 1
        assert section_data[1]["enquiries_outside_sla"] == 0
        assert section_data[1]["enquiries_open"] == 0

    @patch("application.views.settings")
    @patch("application.utils.calculate_business_days", return_value=10)
    def test_closed_outside_sla(self, mock_calc, mock_settings):
        mock_settings.ENQUIRY_SLA_DAYS = 5
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = timezone.now()
        enquiry.created_at = timezone.now() - timedelta(days=14)

        section_data = {}
        section = MagicMock()
        _classify_enquiry_for_sla(enquiry, section_data, 1, "Test Section", section)

        assert section_data[1]["enquiries_within_sla"] == 0
        assert section_data[1]["enquiries_outside_sla"] == 1

    def test_open_enquiry(self):
        enquiry = MagicMock()
        enquiry.status = "open"

        section_data = {}
        section = MagicMock()
        _classify_enquiry_for_sla(enquiry, section_data, 1, "Test Section", section)

        assert section_data[1]["enquiries_open"] == 1
        assert section_data[1]["enquiries_within_sla"] == 0

    def test_new_enquiry(self):
        enquiry = MagicMock()
        enquiry.status = "new"

        section_data = {}
        section = MagicMock()
        _classify_enquiry_for_sla(enquiry, section_data, 1, "Test Section", section)

        assert section_data[1]["enquiries_open"] == 1

    def test_existing_section_data_updated(self):
        section_data = {
            1: {
                "id": 1,
                "name": "Test",
                "section": MagicMock(),
                "enquiries_within_sla": 2,
                "enquiries_outside_sla": 1,
                "enquiries_open": 3,
            }
        }
        enquiry = MagicMock()
        enquiry.status = "open"

        _classify_enquiry_for_sla(enquiry, section_data, 1, "Test", MagicMock())
        assert section_data[1]["enquiries_open"] == 4

    @patch("application.views.settings")
    @patch("application.utils.calculate_business_days", return_value=None)
    def test_closed_with_none_business_days(self, mock_calc, mock_settings):
        mock_settings.ENQUIRY_SLA_DAYS = 5
        enquiry = MagicMock()
        enquiry.status = "closed"
        enquiry.closed_at = timezone.now()
        enquiry.created_at = timezone.now() - timedelta(days=3)

        section_data = {}
        _classify_enquiry_for_sla(enquiry, section_data, 1, "Test", MagicMock())
        # None business_days fails the <= check, so goes to outside_sla
        assert section_data[1]["enquiries_outside_sla"] == 1


class TestFilterActiveSections:
    """Tests for _filter_active_sections."""

    def test_empty_dict(self):
        result = _filter_active_sections({})
        assert result == []

    def test_filters_out_empty_sections(self):
        data = {
            1: {
                "name": "Active",
                "enquiries_within_sla": 1,
                "enquiries_outside_sla": 0,
                "enquiries_open": 0,
            },
            2: {
                "name": "Empty",
                "enquiries_within_sla": 0,
                "enquiries_outside_sla": 0,
                "enquiries_open": 0,
            },
        }
        result = _filter_active_sections(data)
        assert len(result) == 1
        assert result[0]["name"] == "Active"

    def test_sorts_by_name(self):
        data = {
            1: {
                "name": "Zebra",
                "enquiries_within_sla": 1,
                "enquiries_outside_sla": 0,
                "enquiries_open": 0,
            },
            2: {
                "name": "Alpha",
                "enquiries_within_sla": 0,
                "enquiries_outside_sla": 1,
                "enquiries_open": 0,
            },
        }
        result = _filter_active_sections(data)
        assert len(result) == 2
        assert result[0]["name"] == "Alpha"
        assert result[1]["name"] == "Zebra"

    def test_all_types_count_as_active(self):
        data = {
            1: {
                "name": "SLA Only",
                "enquiries_within_sla": 1,
                "enquiries_outside_sla": 0,
                "enquiries_open": 0,
            },
            2: {
                "name": "Outside Only",
                "enquiries_within_sla": 0,
                "enquiries_outside_sla": 1,
                "enquiries_open": 0,
            },
            3: {
                "name": "Open Only",
                "enquiries_within_sla": 0,
                "enquiries_outside_sla": 0,
                "enquiries_open": 1,
            },
        }
        result = _filter_active_sections(data)
        assert len(result) == 3

    def test_none_name_sorts_last(self):
        data = {
            1: {
                "name": None,
                "enquiries_within_sla": 1,
                "enquiries_outside_sla": 0,
                "enquiries_open": 0,
            },
            2: {
                "name": "Alpha",
                "enquiries_within_sla": 1,
                "enquiries_outside_sla": 0,
                "enquiries_open": 0,
            },
        }
        result = _filter_active_sections(data)
        assert result[0]["name"] == "Alpha"
        assert result[1]["name"] is None
