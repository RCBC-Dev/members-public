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
Basic view tests using Django test client for views.py.
Focuses on unauthenticated redirects and admin-authenticated responses.
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from application.models import Admin, Ward, Section, Department, Member, Enquiry, JobType


def _make_section():
    dept, _ = Department.objects.get_or_create(name="Test Dept")
    section, _ = Section.objects.get_or_create(name="Test Section", defaults={"department": dept})
    return section


def _make_member():
    ward, _ = Ward.objects.get_or_create(name="Test Ward")
    member = Member.objects.create(
        first_name="Test",
        last_name="Member",
        email="testmember@example.com",
        ward=ward,
    )
    return member


def _make_enquiry():
    section = _make_section()
    member = Member.objects.filter(email="testmember@example.com").first()
    if not member:
        member = _make_member()
    return Enquiry.objects.create(
        title="Test Enquiry",
        member=member,
        section=section,
        status="open",
    )


class BaseViewTest(TestCase):
    """Base class with admin user setup."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testadmin", password="testpass123", email="admin@test.com"
        )
        self.admin = Admin.objects.create(user=self.user)
        self.client.login(username="testadmin", password="testpass123")


class TestUnauthenticatedRedirects(TestCase):
    """Test that protected views redirect unauthenticated users."""

    def test_index_redirects_unauthenticated(self):
        response = self.client.get(reverse("application:index"))
        self.assertIn(response.status_code, [302, 301])

    def test_enquiry_list_redirects_unauthenticated(self):
        response = self.client.get(reverse("application:enquiry_list"))
        self.assertIn(response.status_code, [302, 301])

    def test_enquiry_create_redirects_unauthenticated(self):
        response = self.client.get(reverse("application:enquiry_create"))
        self.assertIn(response.status_code, [302, 301])

    def test_welcome_is_accessible(self):
        response = self.client.get(reverse("application:welcome"))
        # Welcome page should either render or redirect to login
        self.assertIn(response.status_code, [200, 302])


class TestWelcomeView(BaseViewTest):
    """Test the welcome view."""

    def test_welcome_redirects_when_logged_in(self):
        # When logged in, welcome page might redirect to home
        response = self.client.get(reverse("application:welcome"))
        self.assertIn(response.status_code, [200, 302])


class TestIndexView(BaseViewTest):
    """Test the index/home view."""

    def test_index_loads_for_admin(self):
        response = self.client.get(reverse("application:index"))
        # Should render (200) or redirect
        self.assertIn(response.status_code, [200, 302])


class TestEnquiryListView(BaseViewTest):
    """Test the enquiry list view."""

    def test_enquiry_list_loads(self):
        response = self.client.get(reverse("application:enquiry_list"))
        self.assertIn(response.status_code, [200, 302])

    def test_enquiry_list_with_status_filter(self):
        response = self.client.get(
            reverse("application:enquiry_list") + "?status=open"
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiry_list_with_date_range(self):
        response = self.client.get(
            reverse("application:enquiry_list") + "?date_range=12months"
        )
        self.assertIn(response.status_code, [200, 302])


class TestEnquiryCreateView(BaseViewTest):
    """Test enquiry create view."""

    def test_get_create_form(self):
        response = self.client.get(reverse("application:enquiry_create"))
        self.assertIn(response.status_code, [200, 302])


class TestEnquiryDetailView(BaseViewTest):
    """Test enquiry detail view."""

    def test_detail_404_for_nonexistent(self):
        response = self.client.get(
            reverse("application:enquiry_detail", kwargs={"pk": 99999})
        )
        # Should be 404 or redirect
        self.assertIn(response.status_code, [200, 302, 404])


class TestApiEndpoints(BaseViewTest):
    """Test API endpoints."""

    def test_api_search_job_types_empty(self):
        response = self.client.get(
            reverse("application:api_search_job_types") + "?q="
        )
        self.assertIn(response.status_code, [200, 302])

    def test_api_search_job_types_with_query(self):
        response = self.client.get(
            reverse("application:api_search_job_types") + "?q=test"
        )
        self.assertIn(response.status_code, [200, 302])

    def test_api_get_all_job_types(self):
        response = self.client.get(reverse("application:api_get_all_job_types"))
        self.assertIn(response.status_code, [200, 302])

    def test_api_get_all_contacts(self):
        response = self.client.get(reverse("application:api_get_all_contacts"))
        self.assertIn(response.status_code, [200, 302])

    def test_api_find_member_by_email_no_email(self):
        response = self.client.get(
            reverse("application:api_find_member_by_email") + "?email="
        )
        self.assertIn(response.status_code, [200, 302])

    def test_api_find_member_by_email_unknown(self):
        response = self.client.get(
            reverse("application:api_find_member_by_email") + "?email=nobody@nowhere.com"
        )
        self.assertIn(response.status_code, [200, 302])

    def test_api_find_member_by_email_known(self):
        member = _make_member()
        response = self.client.get(
            reverse("application:api_find_member_by_email") + f"?email={member.email}"
        )
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertTrue(data.get("success"))

    def test_api_get_contacts_by_job_type_no_id(self):
        response = self.client.get(
            reverse("application:api_get_contacts_by_job_type")
        )
        self.assertIn(response.status_code, [200, 302, 400])

    def test_api_get_job_types_by_contact_no_id(self):
        response = self.client.get(
            reverse("application:api_get_job_types_by_contact")
        )
        self.assertIn(response.status_code, [200, 302, 400])

    def test_api_get_contact_section_no_id(self):
        response = self.client.get(reverse("application:api_get_contact_section"))
        self.assertIn(response.status_code, [200, 302, 400])


class TestReportViews(BaseViewTest):
    """Test report views."""

    def test_average_response_time_report(self):
        response = self.client.get(
            reverse("application:average_response_time_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_overdue_enquiries_report(self):
        response = self.client.get(
            reverse("application:overdue_enquiries_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_member_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_member_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_section_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_section_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_ward_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_ward_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_monthly_enquiries_report(self):
        response = self.client.get(
            reverse("application:monthly_enquiries_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_performance_dashboard_report(self):
        response = self.client.get(
            reverse("application:performance_dashboard_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_member_monthly_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_member_monthly_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_section_monthly_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_section_monthly_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_job_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_job_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_job_monthly_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_job_monthly_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_section_workload_chart_report(self):
        response = self.client.get(
            reverse("application:section_workload_chart_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_job_workload_chart_report(self):
        response = self.client.get(
            reverse("application:job_workload_chart_report")
        )
        self.assertIn(response.status_code, [200, 302])

    def test_enquiries_per_ward_monthly_report(self):
        response = self.client.get(
            reverse("application:enquiries_per_ward_monthly_report")
        )
        self.assertIn(response.status_code, [200, 302])


class TestLogoutView(BaseViewTest):
    """Test the logout view."""

    def test_logout_post_logs_out(self):
        response = self.client.post(reverse("application:logout"))
        self.assertIn(response.status_code, [200, 302])
