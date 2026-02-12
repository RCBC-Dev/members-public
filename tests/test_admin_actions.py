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
Tests for admin action functions in application/admin.py
(apply_user_mappings, make_members_inactive, merge_members,
 merge_contacts, merge_job_types, bulk_resize_images)
"""

import pytest
from unittest.mock import MagicMock, patch, call
from django.db.models import ProtectedError

from application.admin import (
    apply_user_mappings,
    make_members_inactive,
    merge_members,
    merge_contacts,
    merge_job_types,
    bulk_resize_images,
)


class TestApplyUserMappings:
    """Tests for apply_user_mappings admin action."""

    def test_applies_primary_unapplied_mappings(self):
        request = MagicMock()
        modeladmin = MagicMock()

        mapping1 = MagicMock()
        mapping1.apply_to_enquiries.return_value = 5
        mapping2 = MagicMock()
        mapping2.apply_to_enquiries.return_value = 3

        queryset = MagicMock()
        queryset.filter.return_value = [mapping1, mapping2]

        with patch("application.admin.messages") as mock_msgs:
            apply_user_mappings(modeladmin, request, queryset)

        mock_msgs.success.assert_called_once()
        msg = mock_msgs.success.call_args[0][1]
        assert "2 mappings" in msg
        assert "8 records" in msg

    def test_no_applicable_mappings(self):
        request = MagicMock()
        modeladmin = MagicMock()

        queryset = MagicMock()
        queryset.filter.return_value = []

        with patch("application.admin.messages") as mock_msgs:
            apply_user_mappings(modeladmin, request, queryset)

        mock_msgs.warning.assert_called_once()

    def test_mapping_with_zero_updates_not_counted(self):
        request = MagicMock()
        modeladmin = MagicMock()

        mapping = MagicMock()
        mapping.apply_to_enquiries.return_value = 0

        queryset = MagicMock()
        queryset.filter.return_value = [mapping]

        with patch("application.admin.messages") as mock_msgs:
            apply_user_mappings(modeladmin, request, queryset)

        mock_msgs.warning.assert_called_once()


class TestMakeMembersInactive:
    """Tests for make_members_inactive admin action."""

    def test_updates_queryset(self):
        request = MagicMock()
        modeladmin = MagicMock()

        queryset = MagicMock()
        queryset.update.return_value = 3

        with patch("application.admin.messages") as mock_msgs:
            make_members_inactive(modeladmin, request, queryset)

        queryset.update.assert_called_once_with(is_active=False)
        mock_msgs.success.assert_called_once()
        msg = mock_msgs.success.call_args[0][1]
        assert "3 member(s)" in msg


class TestMergeMembers:
    """Tests for merge_members admin action."""

    @patch("application.admin._validate_merge_selection", return_value=None)
    def test_invalid_selection_returns_early(self, mock_validate):
        request = MagicMock()
        modeladmin = MagicMock()
        queryset = MagicMock()

        merge_members(modeladmin, request, queryset)
        mock_validate.assert_called_once()

    @patch("application.admin.transaction")
    @patch("application.admin.Enquiry")
    @patch("application.admin._report_merge_success")
    @patch("application.admin._delete_duplicate_and_report")
    @patch("application.admin._validate_merge_selection")
    def test_successful_merge(
        self, mock_validate, mock_delete, mock_report, mock_enquiry, mock_tx
    ):
        request = MagicMock()
        modeladmin = MagicMock()
        queryset = MagicMock()

        primary = MagicMock()
        primary.id = 1
        primary.full_name = "John"
        duplicate = MagicMock()
        duplicate.id = 2
        duplicate.full_name = "Jon"

        mock_validate.return_value = [primary, duplicate]
        mock_enquiry.objects.filter.return_value.update.return_value = 5
        mock_delete.return_value = ("Jon", 2)

        merge_members(modeladmin, request, queryset)
        mock_delete.assert_called_once()
        mock_report.assert_called_once()

    @patch("application.admin.transaction")
    @patch("application.admin._delete_duplicate_and_report", return_value=None)
    @patch("application.admin._validate_merge_selection")
    @patch("application.admin.Enquiry")
    def test_protected_error_during_delete(
        self, mock_enquiry, mock_validate, mock_delete, mock_tx
    ):
        request = MagicMock()
        modeladmin = MagicMock()
        queryset = MagicMock()

        primary = MagicMock()
        primary.id = 1
        duplicate = MagicMock()
        duplicate.id = 2

        mock_validate.return_value = [primary, duplicate]
        mock_enquiry.objects.filter.return_value.update.return_value = 0

        merge_members(modeladmin, request, queryset)
        mock_delete.assert_called_once()

    @patch("application.admin.transaction")
    @patch("application.admin._validate_merge_selection")
    @patch("application.admin.Enquiry")
    def test_exception_during_merge(self, mock_enquiry, mock_validate, mock_tx):
        request = MagicMock()
        modeladmin = MagicMock()
        queryset = MagicMock()

        primary = MagicMock()
        primary.id = 1
        duplicate = MagicMock()
        duplicate.id = 2

        mock_validate.return_value = [primary, duplicate]
        mock_enquiry.objects.filter.side_effect = Exception("DB error")

        with patch("application.admin.messages") as mock_msgs:
            merge_members(modeladmin, request, queryset)
        mock_msgs.error.assert_called_once()
        assert "DB error" in mock_msgs.error.call_args[0][1]


class TestMergeContacts:
    """Tests for merge_contacts admin action."""

    @patch("application.admin._validate_merge_selection", return_value=None)
    def test_invalid_selection_returns_early(self, mock_validate):
        merge_contacts(MagicMock(), MagicMock(), MagicMock())
        mock_validate.assert_called_once()

    @patch("application.admin.transaction")
    @patch("application.admin.Enquiry")
    @patch("application.admin._report_merge_success")
    @patch("application.admin._delete_duplicate_and_report")
    @patch("application.admin._validate_merge_selection")
    def test_successful_merge_copies_job_types(
        self, mock_validate, mock_delete, mock_report, mock_enquiry, mock_tx
    ):
        request = MagicMock()
        primary = MagicMock()
        primary.id = 1
        primary.name = "Primary Contact"
        duplicate = MagicMock()
        duplicate.id = 2
        duplicate.name = "Duplicate Contact"

        jt1 = MagicMock()
        jt2 = MagicMock()
        duplicate.job_types.all.return_value = [jt1, jt2]

        mock_validate.return_value = [primary, duplicate]
        mock_enquiry.objects.filter.return_value.update.return_value = 3
        mock_delete.return_value = ("Duplicate Contact", 2)

        merge_contacts(MagicMock(), request, MagicMock())

        # Job types should be copied to primary
        primary.job_types.add.assert_any_call(jt1)
        primary.job_types.add.assert_any_call(jt2)
        mock_report.assert_called_once()


class TestMergeJobTypes:
    """Tests for merge_job_types admin action."""

    @patch("application.admin._validate_merge_selection", return_value=None)
    def test_invalid_selection_returns_early(self, mock_validate):
        merge_job_types(MagicMock(), MagicMock(), MagicMock())

    @patch("application.admin.transaction")
    @patch("application.admin.Enquiry")
    @patch("application.admin._reassign_contacts_job_type", return_value=2)
    @patch("application.admin._report_merge_success")
    @patch("application.admin._delete_duplicate_and_report")
    @patch("application.admin._validate_merge_selection")
    def test_successful_merge_reassigns_contacts(
        self, mock_validate, mock_delete, mock_report, mock_reassign, mock_enquiry, mock_tx
    ):
        request = MagicMock()
        primary = MagicMock()
        primary.id = 1
        primary.name = "Primary JT"
        duplicate = MagicMock()
        duplicate.id = 2
        duplicate.name = "Dup JT"

        mock_validate.return_value = [primary, duplicate]
        mock_enquiry.objects.filter.return_value.update.return_value = 1
        mock_delete.return_value = ("Dup JT", 2)

        with patch("application.admin.messages") as mock_msgs:
            merge_job_types(MagicMock(), request, MagicMock())

        mock_reassign.assert_called_once_with(duplicate, primary)
        # Should report contact updates
        assert mock_msgs.success.call_count >= 1


class TestBulkResizeImages:
    """Tests for bulk_resize_images admin action."""

    @patch("application.admin._report_resize_results")
    @patch("application.admin._should_skip_attachment", return_value=True)
    def test_all_skipped(self, mock_skip, mock_report):
        request = MagicMock()
        att1 = MagicMock()
        att2 = MagicMock()

        bulk_resize_images(MagicMock(), request, [att1, att2])

        mock_report.assert_called_once_with(request, 0, 2, 0, 0)

    @patch("application.admin._report_resize_results")
    @patch("application.admin._resize_attachment", return_value=(5000, True))
    @patch("application.admin._should_skip_attachment", return_value=False)
    def test_all_resized(self, mock_skip, mock_resize, mock_report):
        request = MagicMock()
        att1 = MagicMock()
        att2 = MagicMock()

        bulk_resize_images(MagicMock(), request, [att1, att2])

        mock_report.assert_called_once_with(request, 2, 0, 0, 10000)

    @patch("application.admin._report_resize_results")
    @patch("application.admin._resize_attachment", return_value=(0, False))
    @patch("application.admin._should_skip_attachment", return_value=False)
    def test_not_resized_counts_as_skipped(self, mock_skip, mock_resize, mock_report):
        request = MagicMock()
        att1 = MagicMock()

        bulk_resize_images(MagicMock(), request, [att1])

        mock_report.assert_called_once_with(request, 0, 1, 0, 0)

    @patch("application.admin._report_resize_results")
    @patch("application.admin._resize_attachment", side_effect=Exception("fail"))
    @patch("application.admin._should_skip_attachment", return_value=False)
    def test_error_during_resize(self, mock_skip, mock_resize, mock_report):
        request = MagicMock()
        att1 = MagicMock()

        bulk_resize_images(MagicMock(), request, [att1])

        mock_report.assert_called_once_with(request, 0, 0, 1, 0)

    @patch("application.admin._report_resize_results")
    @patch("application.admin._resize_attachment")
    @patch("application.admin._should_skip_attachment")
    def test_mixed_results(self, mock_skip, mock_resize, mock_report):
        request = MagicMock()
        att1 = MagicMock()
        att2 = MagicMock()
        att3 = MagicMock()

        mock_skip.side_effect = [True, False, False]
        mock_resize.side_effect = [(3000, True), Exception("oops")]

        bulk_resize_images(MagicMock(), request, [att1, att2, att3])

        mock_report.assert_called_once_with(request, 1, 1, 1, 3000)
