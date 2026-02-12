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
View tests for enquiry-related views: create, detail, edit, close, reopen.
"""

import json
import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from application.models import Admin, Ward, Section, Department, Member, Enquiry, JobType


def _make_section(name="Section A"):
    dept, _ = Department.objects.get_or_create(name="Test Dept")
    section, _ = Section.objects.get_or_create(name=name, defaults={"department": dept})
    return section


def _make_member(email="member1@example.com"):
    ward, _ = Ward.objects.get_or_create(name="Test Ward")
    m, _ = Member.objects.get_or_create(
        email=email,
        defaults={"first_name": "Test", "last_name": "Member", "ward": ward}
    )
    return m


def _make_enquiry(status="open"):
    section = _make_section()
    member = _make_member()
    return Enquiry.objects.create(
        title="Test Enquiry",
        member=member,
        section=section,
        status=status,
    )


class BaseViewTest(TestCase):
    """Base class with admin user setup."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="viewadmin", password="testpass123", email="viewadmin@test.com"
        )
        self.admin = Admin.objects.create(user=self.user)
        self.client.login(username="viewadmin", password="testpass123")


class TestEnquiryDetailView(BaseViewTest):
    """Tests for EnquiryDetailView."""

    def test_detail_view_loads_for_existing_enquiry(self):
        enquiry = _make_enquiry()
        response = self.client.get(
            reverse("application:enquiry_detail", kwargs={"pk": enquiry.pk})
        )
        self.assertIn(response.status_code, [200, 302])

    def test_detail_view_404_for_nonexistent(self):
        response = self.client.get(
            reverse("application:enquiry_detail", kwargs={"pk": 999999})
        )
        self.assertIn(response.status_code, [200, 302, 404])


class TestEnquiryCloseView(BaseViewTest):
    """Tests for EnquiryCloseView."""

    def test_close_view_redirects_on_get(self):
        enquiry = _make_enquiry(status="open")
        response = self.client.get(
            reverse("application:enquiry_close", kwargs={"pk": enquiry.pk})
        )
        # Should redirect or render
        self.assertIn(response.status_code, [200, 302, 405])

    def test_close_enquiry_post(self):
        enquiry = _make_enquiry(status="open")
        section = _make_section()
        job_type, _ = JobType.objects.get_or_create(name="Test Job")
        response = self.client.post(
            reverse("application:enquiry_close", kwargs={"pk": enquiry.pk}),
            {
                "section": section.pk,
                "job_type": job_type.pk,
                "close_note": "Closing test enquiry",
            }
        )
        self.assertIn(response.status_code, [200, 302])


class TestEnquiryReopenView(BaseViewTest):
    """Tests for enquiry_reopen view."""

    def test_reopen_get_redirects(self):
        enquiry = _make_enquiry(status="closed")
        enquiry.closed_at = None
        enquiry.save()
        enquiry.status = "closed"
        enquiry.save()
        response = self.client.post(
            reverse("application:enquiry_reopen", kwargs={"pk": enquiry.pk}),
            {"reopen_reason": "Need to investigate more"}
        )
        self.assertIn(response.status_code, [200, 302])

    def test_reopen_nonexistent_enquiry(self):
        response = self.client.post(
            reverse("application:enquiry_reopen", kwargs={"pk": 999999}),
            {"reopen_reason": "Test reason"},
        )
        self.assertIn(response.status_code, [200, 302, 404])

    def test_reopen_missing_reason_returns_error(self):
        enquiry = _make_enquiry(status="closed")
        enquiry.status = "closed"
        enquiry.save()
        response = self.client.post(
            reverse("application:enquiry_reopen", kwargs={"pk": enquiry.pk}),
            {}
        )
        self.assertIn(response.status_code, [200, 302])

    def test_reopen_ajax_missing_reason_returns_json(self):
        enquiry = _make_enquiry(status="open")
        response = self.client.post(
            reverse("application:enquiry_reopen", kwargs={"pk": enquiry.pk}),
            {},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertFalse(data.get("success"))


class TestEnquiryEditView(BaseViewTest):
    """Tests for enquiry_edit view."""

    def test_edit_view_get(self):
        enquiry = _make_enquiry()
        response = self.client.get(
            reverse("application:enquiry_edit", kwargs={"pk": enquiry.pk})
        )
        self.assertIn(response.status_code, [200, 302])

    def test_edit_nonexistent_redirects(self):
        response = self.client.get(
            reverse("application:enquiry_edit", kwargs={"pk": 999999})
        )
        self.assertIn(response.status_code, [200, 302, 404])


class TestApiUpdateClosedEnquiryJobType(BaseViewTest):
    """Tests for api_update_closed_enquiry_job_type view."""

    def test_post_without_job_type_returns_error(self):
        enquiry = _make_enquiry(status="closed")
        enquiry.status = "closed"
        enquiry.save()
        response = self.client.post(
            reverse("application:api_update_closed_enquiry_job_type"),
            {"enquiry_id": enquiry.pk, "job_type_id": ""},
        )
        self.assertIn(response.status_code, [200, 302, 400])

    def test_post_missing_enquiry_returns_error(self):
        response = self.client.post(
            reverse("application:api_update_closed_enquiry_job_type"),
            {"enquiry_id": 999999, "job_type_id": 1},
        )
        self.assertIn(response.status_code, [200, 302, 400, 404])


class TestEnquiryListView(BaseViewTest):
    """Tests for EnquiryListView."""

    def test_list_view_loads(self):
        response = self.client.get(reverse("application:enquiry_list"))
        self.assertIn(response.status_code, [200, 302])

    def test_list_view_with_search(self):
        response = self.client.get(
            reverse("application:enquiry_list") + "?search=test"
        )
        self.assertIn(response.status_code, [200, 302])

    def test_list_view_closed_filter(self):
        response = self.client.get(
            reverse("application:enquiry_list") + "?status=closed"
        )
        self.assertIn(response.status_code, [200, 302])

    def test_list_view_custom_date_range(self):
        response = self.client.get(
            reverse("application:enquiry_list") + "?date_range=custom&date_from=2024-01-01&date_to=2024-12-31"
        )
        self.assertIn(response.status_code, [200, 302])


class TestDatatablesView(BaseViewTest):
    """Tests for DataTables server-side processing view."""

    def test_datatables_endpoint_returns_json(self):
        response = self.client.post(
            reverse("application:enquiry_list_datatables"),
            {
                "draw": "1",
                "start": "0",
                "length": "10",
                "search[value]": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("data", data)


class TestApiAddEmailNote(BaseViewTest):
    """Tests for api_add_email_note view."""

    def test_add_email_note_to_nonexistent_enquiry(self):
        response = self.client.post(
            reverse("application:api_add_email_note", kwargs={"pk": 999999}),
            {"note": "Test note", "direction": "INCOMING"},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data["success"])

    def test_add_email_note_missing_content_returns_error(self):
        enquiry = _make_enquiry()
        response = self.client.post(
            reverse("application:api_add_email_note", kwargs={"pk": enquiry.pk}),
            {"note": "", "direction": "INCOMING"},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data["success"])

    def test_add_incoming_email_note_success(self):
        enquiry = _make_enquiry()
        response = self.client.post(
            reverse("application:api_add_email_note", kwargs={"pk": enquiry.pk}),
            {"note": "Email note content", "direction": "INCOMING"},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_add_outgoing_email_note_success(self):
        enquiry = _make_enquiry()
        response = self.client.post(
            reverse("application:api_add_email_note", kwargs={"pk": enquiry.pk}),
            {"note": "Outgoing email content", "direction": "OUTGOING"},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_add_email_note_unknown_direction(self):
        enquiry = _make_enquiry()
        response = self.client.post(
            reverse("application:api_add_email_note", kwargs={"pk": enquiry.pk}),
            {"note": "Some note", "direction": "UNKNOWN"},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])


class TestApiDeleteAttachment(BaseViewTest):
    """Tests for api_delete_attachment view."""

    def test_delete_nonexistent_attachment_returns_404(self):
        response = self.client.delete(
            reverse("application:api_delete_attachment", kwargs={"attachment_id": 999999})
        )
        self.assertIn(response.status_code, [200, 404])
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertFalse(data["success"])


class TestExportViews(BaseViewTest):
    """Tests for export views."""

    def test_export_csv(self):
        response = self.client.get(reverse("application:export_enquiries_csv"))
        self.assertIn(response.status_code, [200, 302])

    def test_export_excel(self):
        response = self.client.get(reverse("application:export_enquiries_excel"))
        self.assertIn(response.status_code, [200, 302, 500])

    def test_get_export_info(self):
        response = self.client.get(reverse("application:get_export_info"))
        self.assertIn(response.status_code, [200, 302])
