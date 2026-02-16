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
Tests for application/report_mixins.py
"""

from django.test import TestCase, RequestFactory
from django.utils import timezone
from datetime import timedelta, datetime
from application.models import Department, Section, Ward, Member, Enquiry
from application.report_mixins import (
    ResponseTimeReportMixin,
    OverdueReportMixin,
    CountReportMixin,
    MonthlyReportMixin,
    EnquiryListReportMixin,
)


def _make_section(name="Test Section"):
    dept, _ = Department.objects.get_or_create(name="Test Dept")
    section, _ = Section.objects.get_or_create(name=name, defaults={"department": dept})
    return section


def _make_member():
    ward, _ = Ward.objects.get_or_create(name="Test Ward")
    m, _ = Member.objects.get_or_create(
        email="reporttest@example.com",
        defaults={"first_name": "Report", "last_name": "Tester", "ward": ward},
    )
    return m


def _make_request(params=None):
    rf = RequestFactory()
    return rf.get("/", params or {})


class MockResponseTimeView(ResponseTimeReportMixin):
    def __init__(self, request):
        self.request = request


class MockOverdueView(OverdueReportMixin):
    def __init__(self, request):
        self.request = request


class MockCountView(CountReportMixin):
    def __init__(self, request):
        self.request = request


class MockMonthlyView(MonthlyReportMixin):
    def __init__(self, request):
        self.request = request


class MockEnquiryListView(EnquiryListReportMixin):
    def __init__(self, request):
        self.request = request


class TestResponseTimeReportMixin(TestCase):

    def test_get_response_time_queryset_no_filters(self):
        request = _make_request()
        view = MockResponseTimeView(request)
        enquiries, date_info = view.get_response_time_queryset()
        self.assertIsNotNone(enquiries)
        self.assertIn("months", date_info)

    def test_get_response_time_queryset_with_start_date(self):
        request = _make_request({"start_date": "2024-01-01", "months": "12"})
        view = MockResponseTimeView(request)
        enquiries, date_info = view.get_response_time_queryset()
        self.assertEqual(date_info["start_date"], "2024-01-01")

    def test_get_response_time_queryset_with_date_range(self):
        request = _make_request({"start_date": "2024-01-01", "end_date": "2024-12-31"})
        view = MockResponseTimeView(request)
        enquiries, date_info = view.get_response_time_queryset()
        self.assertEqual(date_info["end_date"], "2024-12-31")

    def test_get_response_time_queryset_with_member_filter(self):
        request = _make_request({"member": "999"})
        view = MockResponseTimeView(request)
        enquiries, date_info = view.get_response_time_queryset()
        self.assertIsNotNone(enquiries)

    def test_get_response_time_queryset_with_section_filter(self):
        request = _make_request({"section": "999"})
        view = MockResponseTimeView(request)
        enquiries, date_info = view.get_response_time_queryset()
        self.assertIsNotNone(enquiries)


class TestOverdueReportMixin(TestCase):

    def setUp(self):
        self.section = _make_section()
        self.member = _make_member()

    def test_get_overdue_queryset_returns_list(self):
        request = _make_request()
        view = MockOverdueView(request)
        result, threshold = view.get_overdue_queryset()
        self.assertIsInstance(result, list)
        self.assertEqual(threshold, 5)

    def test_get_overdue_queryset_custom_threshold(self):
        request = _make_request()
        view = MockOverdueView(request)
        result, threshold = view.get_overdue_queryset(threshold_days=10)
        self.assertEqual(threshold, 10)

    def test_get_overdue_queryset_with_member_filter(self):
        request = _make_request({"member": "1"})
        view = MockOverdueView(request)
        result, threshold = view.get_overdue_queryset()
        self.assertIsInstance(result, list)

    def test_get_overdue_queryset_with_section_filter(self):
        request = _make_request({"section": "1"})
        view = MockOverdueView(request)
        result, threshold = view.get_overdue_queryset()
        self.assertIsInstance(result, list)

    def test_get_overdue_queryset_old_enquiry_included(self):
        old_enquiry = Enquiry.objects.create(
            title="Old Enquiry",
            member=self.member,
            section=self.section,
            status="open",
        )
        Enquiry.objects.filter(pk=old_enquiry.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )
        request = _make_request()
        view = MockOverdueView(request)
        result, threshold = view.get_overdue_queryset()
        ids = [e.pk for e in result]
        self.assertIn(old_enquiry.pk, ids)


class TestCountReportMixin(TestCase):

    def test_get_count_data_for_member(self):
        request = _make_request()
        view = MockCountView(request)
        objects, date_from, months = view.get_count_data(Member, "enquiries", months=12)
        self.assertIsNotNone(objects)
        self.assertEqual(months, 12)

    def test_get_count_data_for_section(self):
        request = _make_request()
        view = MockCountView(request)
        objects, date_from, months = view.get_count_data(Section, "enquiries", months=6)
        self.assertEqual(months, 6)

    def test_get_count_data_for_ward(self):
        request = _make_request()
        view = MockCountView(request)
        objects, date_from, months = view.get_count_data(
            Ward, "members__enquiries", months=3
        )
        self.assertEqual(months, 3)


class TestMonthlyReportMixin(TestCase):

    def setUp(self):
        self.section = _make_section()
        self.member = _make_member()

    def test_get_monthly_data_no_month(self):
        request = _make_request()
        view = MockMonthlyView(request)
        data = view.get_monthly_data()
        self.assertIn("selected_month", data)
        self.assertIn("month_start", data)
        self.assertIn("month_end", data)
        self.assertIn("months_list", data)

    def test_get_monthly_data_with_valid_month(self):
        request = _make_request()
        view = MockMonthlyView(request)
        data = view.get_monthly_data("2024-06")
        self.assertEqual(data["selected_month"], "2024-06")

    def test_get_monthly_data_december_range(self):
        request = _make_request()
        view = MockMonthlyView(request)
        data = view.get_monthly_data("2023-12")
        self.assertEqual(data["selected_month"], "2023-12")
        self.assertEqual(data["month_end"].month, 1)

    def test_get_monthly_data_invalid_month_fallback(self):
        request = _make_request()
        view = MockMonthlyView(request)
        data = view.get_monthly_data("not-a-month")
        self.assertIsNotNone(data["selected_month"])

    def test_make_section_entry(self):
        request = _make_request()
        view = MockMonthlyView(request)
        section = _make_section()
        entry = view._make_section_entry(section)
        self.assertEqual(entry["enquiries_within_sla"], 0)
        self.assertEqual(entry["enquiries_outside_sla"], 0)
        self.assertEqual(entry["enquiries_open"], 0)

    def test_make_section_entry_none(self):
        request = _make_request()
        view = MockMonthlyView(request)
        entry = view._make_section_entry(None)
        self.assertEqual(entry["name"], "Unassigned")

    def test_classify_closed_enquiry(self):
        request = _make_request()
        view = MockMonthlyView(request)
        enquiry = Enquiry.objects.create(
            title="SLA Test",
            member=self.member,
            section=self.section,
            status="closed",
        )
        Enquiry.objects.filter(pk=enquiry.pk).update(
            created_at=timezone.now() - timedelta(days=3),
            closed_at=timezone.now() - timedelta(days=1),
        )
        enquiry.refresh_from_db()
        entry = {
            "enquiries_within_sla": 0,
            "enquiries_outside_sla": 0,
            "enquiries_open": 0,
        }
        view._classify_closed_enquiry(entry, enquiry, sla_days=5)
        total = entry["enquiries_within_sla"] + entry["enquiries_outside_sla"]
        self.assertEqual(total, 1)

    def test_has_any_enquiries_true(self):
        request = _make_request()
        view = MockMonthlyView(request)
        entry = {
            "enquiries_within_sla": 1,
            "enquiries_outside_sla": 0,
            "enquiries_open": 0,
        }
        self.assertTrue(view._has_any_enquiries(entry))

    def test_has_any_enquiries_false(self):
        request = _make_request()
        view = MockMonthlyView(request)
        entry = {
            "enquiries_within_sla": 0,
            "enquiries_outside_sla": 0,
            "enquiries_open": 0,
        }
        self.assertFalse(view._has_any_enquiries(entry))

    def test_get_sla_sections_empty(self):
        request = _make_request()
        view = MockMonthlyView(request)
        month_start = timezone.make_aware(datetime(2020, 1, 1))
        month_end = timezone.make_aware(datetime(2020, 2, 1))
        sections = view.get_sla_sections(month_start, month_end)
        self.assertIsInstance(sections, list)

    def test_get_sla_sections_with_open_enquiry(self):
        request = _make_request()
        view = MockMonthlyView(request)
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        Enquiry.objects.create(
            title="SLA Monthly Test",
            member=self.member,
            section=self.section,
            status="open",
        )
        sections = view.get_sla_sections(month_start, month_end)
        self.assertIsInstance(sections, list)
        self.assertGreater(len(sections), 0)


class TestEnquiryListReportMixin(TestCase):

    def setUp(self):
        self.section = _make_section()
        self.member = _make_member()

    def test_get_enquiry_list_no_filters(self):
        request = _make_request()
        view = MockEnquiryListView(request)
        enquiries = view.get_enquiry_list()
        self.assertIsNotNone(enquiries)

    def test_get_enquiry_list_with_filter(self):
        Enquiry.objects.create(
            title="List Test",
            member=self.member,
            section=self.section,
            status="open",
        )
        request = _make_request()
        view = MockEnquiryListView(request)
        enquiries = view.get_enquiry_list(status="open")
        self.assertIsNotNone(enquiries)

    def test_get_enquiry_list_returns_ordered(self):
        request = _make_request()
        view = MockEnquiryListView(request)
        enquiries = view.get_enquiry_list()
        self.assertIsNotNone(enquiries)
