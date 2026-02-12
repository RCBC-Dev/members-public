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
Tests for pure-logic helper functions in application/admin.py
"""

import pytest
from unittest.mock import MagicMock, patch
from django.db.models import ProtectedError

from unittest.mock import mock_open

from application.admin import (
    _format_protected_object,
    _collect_protected_objects,
    _validate_merge_selection,
    _report_merge_success,
    _format_bytes,
    _should_skip_attachment,
    _resize_attachment,
    _report_resize_results,
    _report_protected_error,
    _delete_duplicate_and_report,
    _reassign_contacts_job_type,
)


class TestFormatProtectedObject:
    """Tests for _format_protected_object."""

    def test_model_with_meta_and_pk(self):
        obj = MagicMock()
        obj._meta.verbose_name = "enquiry"
        obj.pk = 42
        result = _format_protected_object(obj)
        assert "enquiry" in result
        assert "42" in result

    def test_model_without_pk_falls_back_to_str(self):
        # When _meta exists but pk does not, falls through to str(obj)
        class NoMeta:
            def __str__(self):
                return "fallback text"
        result = _format_protected_object(NoMeta())
        assert result == "fallback text"

    def test_plain_string_object(self):
        result = _format_protected_object("simple string")
        assert result == "simple string"

    def test_object_without_meta(self):
        class NoMeta:
            def __str__(self):
                return "no meta object"

        result = _format_protected_object(NoMeta())
        assert result == "no meta object"


class TestCollectProtectedObjects:
    """Tests for _collect_protected_objects."""

    def test_empty_set_returns_empty_list(self):
        result = _collect_protected_objects([])
        assert result == []

    def test_single_model_object(self):
        # Use a plain object without __len__ so it goes to the append path
        class FakeModel:
            _meta = type("Meta", (), {"verbose_name": "section"})()
            pk = 1
            def __str__(self):
                return "FakeModel"
        result = _collect_protected_objects([FakeModel()])
        assert len(result) == 1
        assert "section" in result[0]

    def test_iterable_of_objects_in_set(self):
        # A list in the protected_objects triggers the extend path
        class FakeModel:
            _meta = type("Meta", (), {"verbose_name": "ward"})()
            pk = 5
        result = _collect_protected_objects([[FakeModel()]])
        assert len(result) == 1
        assert "ward" in result[0]

    def test_multiple_objects(self):
        class FakeModel:
            def __init__(self, name, pk):
                self._meta = type("Meta", (), {"verbose_name": name})()
                self.pk = pk
        objs = [FakeModel(f"model{i}", i) for i in range(3)]
        result = _collect_protected_objects(objs)
        assert len(result) == 3


class TestValidateMergeSelection:
    """Tests for _validate_merge_selection."""

    def _make_request(self):
        req = MagicMock()
        req.method = "POST"
        return req

    def test_exactly_two_items_returns_list(self):
        items = [MagicMock(id=1), MagicMock(id=2)]
        qs = MagicMock()
        qs.order_by.return_value = items
        req = self._make_request()
        with patch("application.admin.messages") as mock_msgs:
            result = _validate_merge_selection(req, qs, "wards")
        assert result is not None
        assert len(result) == 2

    def test_one_item_returns_none_with_error(self):
        items = [MagicMock(id=1)]
        qs = MagicMock()
        qs.order_by.return_value = items
        req = self._make_request()
        with patch("application.admin.messages") as mock_msgs:
            result = _validate_merge_selection(req, qs, "wards")
        assert result is None
        mock_msgs.error.assert_called_once()

    def test_three_items_returns_none_with_error(self):
        items = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
        qs = MagicMock()
        qs.order_by.return_value = items
        req = self._make_request()
        with patch("application.admin.messages") as mock_msgs:
            result = _validate_merge_selection(req, qs, "sections")
        assert result is None
        mock_msgs.error.assert_called_once()

    def test_empty_queryset_returns_none(self):
        qs = MagicMock()
        qs.order_by.return_value = []
        req = self._make_request()
        with patch("application.admin.messages"):
            result = _validate_merge_selection(req, qs, "members")
        assert result is None


class TestReportMergeSuccess:
    """Tests for _report_merge_success."""

    def _make_request(self):
        return MagicMock()

    def test_sends_success_message(self):
        req = self._make_request()
        with patch("application.admin.messages") as mock_msgs:
            _report_merge_success(req, "OldWard", 99, "NewWard", 0)
        mock_msgs.success.assert_called()

    def test_no_extra_message_when_no_enquiries_moved(self):
        req = self._make_request()
        with patch("application.admin.messages") as mock_msgs:
            _report_merge_success(req, "OldWard", 99, "NewWard", 0)
        # Only 1 success message (no enquiries moved)
        assert mock_msgs.success.call_count == 1

    def test_extra_message_when_enquiries_moved(self):
        req = self._make_request()
        with patch("application.admin.messages") as mock_msgs:
            _report_merge_success(req, "OldWard", 99, "NewWard", 5)
        # 2 success messages: merge + enquiries moved
        assert mock_msgs.success.call_count == 2

    def test_message_contains_names(self):
        req = self._make_request()
        calls = []
        with patch("application.admin.messages") as mock_msgs:
            mock_msgs.success.side_effect = lambda r, msg: calls.append(msg)
            _report_merge_success(req, "OldName", 42, "NewName", 3)
        combined = " ".join(calls)
        assert "OldName" in combined
        assert "NewName" in combined


class TestFormatBytes:
    """Tests for _format_bytes."""

    def test_kilobytes(self):
        result = _format_bytes(512)
        assert "KB" in result

    def test_megabytes(self):
        result = _format_bytes(2 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = _format_bytes(2 * 1024 * 1024 * 1024)
        assert "GB" in result

    def test_exactly_1mb_boundary(self):
        result = _format_bytes(1024 * 1024 + 1)
        assert "MB" in result

    def test_exactly_1gb_boundary(self):
        result = _format_bytes(1024 * 1024 * 1024 + 1)
        assert "GB" in result

    def test_small_bytes_shows_kb(self):
        result = _format_bytes(100)
        assert "KB" in result
        assert "0.1" in result


class TestShouldSkipAttachment:
    """Tests for _should_skip_attachment."""

    def _make_attachment(self, filename, file_name="uploads/test.jpg"):
        att = MagicMock()
        att.filename = filename
        att.file.name = file_name
        return att

    @patch("django.conf.settings")
    def test_non_image_extension_returns_true(self, mock_settings):
        mock_settings.MEDIA_ROOT = "C:\\fake\\media"
        att = self._make_attachment("document.pdf", "uploads/document.pdf")
        assert _should_skip_attachment(att) is True

    @patch("os.path.exists", return_value=False)
    @patch("django.conf.settings")
    def test_image_file_does_not_exist_returns_true(self, mock_settings, mock_exists):
        mock_settings.MEDIA_ROOT = "C:\\fake\\media"
        att = self._make_attachment("photo.jpg", "uploads/photo.jpg")
        assert _should_skip_attachment(att) is True

    @patch("os.path.getsize", return_value=1024)
    @patch("os.path.exists", return_value=True)
    @patch("django.conf.settings")
    def test_image_small_file_returns_true(self, mock_settings, mock_exists, mock_size):
        mock_settings.MEDIA_ROOT = "C:\\fake\\media"
        att = self._make_attachment("photo.png", "uploads/photo.png")
        assert _should_skip_attachment(att) is True

    @patch("os.path.getsize", return_value=3 * 1024 * 1024)
    @patch("os.path.exists", return_value=True)
    @patch("django.conf.settings")
    def test_image_large_file_returns_false(self, mock_settings, mock_exists, mock_size):
        mock_settings.MEDIA_ROOT = "C:\\fake\\media"
        att = self._make_attachment("photo.jpeg", "uploads/photo.jpeg")
        assert _should_skip_attachment(att) is False


class TestResizeAttachment:
    """Tests for _resize_attachment."""

    def _make_attachment(self, file_name="uploads/photo.jpg"):
        att = MagicMock()
        att.file.name = file_name
        return att

    @patch("application.utils._resize_image_if_needed")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake-image-data")
    @patch("os.path.getsize", return_value=5000)
    @patch("django.conf.settings")
    def test_not_resized_returns_zero_false(
        self, mock_settings, mock_getsize, mock_file, mock_resize
    ):
        mock_settings.MEDIA_ROOT = "C:\\fake\\media"
        mock_resize.return_value = (b"fake-image-data", False, 5000)
        att = self._make_attachment()

        saved, was_resized = _resize_attachment(att)
        assert saved == 0
        assert was_resized is False

    @patch("application.utils._resize_image_if_needed")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake-image-data")
    @patch("os.path.getsize", return_value=5000)
    @patch("django.conf.settings")
    def test_resized_writes_file_and_updates_attachment(
        self, mock_settings, mock_getsize, mock_file, mock_resize
    ):
        mock_settings.MEDIA_ROOT = "C:\\fake\\media"
        mock_resize.return_value = (b"smaller-data", True, 3000)
        att = self._make_attachment()

        saved, was_resized = _resize_attachment(att)
        assert saved == 2000  # 5000 - 3000
        assert was_resized is True
        att.save.assert_called_once_with(update_fields=["file_size"])
        assert att.file_size == 3000


class TestReportResizeResults:
    """Tests for _report_resize_results."""

    def test_resized_only_calls_success(self):
        req = MagicMock()
        with patch("application.admin.messages") as mock_msgs:
            _report_resize_results(req, 3, 0, 0, 1024 * 1024)
        mock_msgs.success.assert_called_once()
        msg = mock_msgs.success.call_args[0][1]
        assert "Resized 3 images" in msg

    def test_skipped_only_calls_success(self):
        req = MagicMock()
        with patch("application.admin.messages") as mock_msgs:
            _report_resize_results(req, 0, 5, 0, 0)
        mock_msgs.success.assert_called_once()
        msg = mock_msgs.success.call_args[0][1]
        assert "Skipped 5 files" in msg

    def test_errors_only_calls_success(self):
        req = MagicMock()
        with patch("application.admin.messages") as mock_msgs:
            _report_resize_results(req, 0, 0, 2, 0)
        mock_msgs.success.assert_called_once()
        msg = mock_msgs.success.call_args[0][1]
        assert "2 errors occurred" in msg

    def test_all_zero_calls_info(self):
        req = MagicMock()
        with patch("application.admin.messages") as mock_msgs:
            _report_resize_results(req, 0, 0, 0, 0)
        mock_msgs.info.assert_called_once()
        msg = mock_msgs.info.call_args[0][1]
        assert "No images were processed." in msg

    def test_multiple_parts_joined_by_pipe(self):
        req = MagicMock()
        with patch("application.admin.messages") as mock_msgs:
            _report_resize_results(req, 2, 3, 1, 2 * 1024 * 1024)
        mock_msgs.success.assert_called_once()
        msg = mock_msgs.success.call_args[0][1]
        assert " | " in msg
        assert "Resized 2 images" in msg
        assert "Skipped 3 files" in msg
        assert "1 errors occurred" in msg


class TestReportProtectedError:
    """Tests for _report_protected_error."""

    def _make_fake_model(self, pk):
        """Create a simple fake model object without __len__."""

        class FakeModel:
            def __init__(self, pk_val):
                self._meta = type("Meta", (), {"verbose_name": "enquiry"})()
                self.pk = pk_val

        return FakeModel(pk)

    def _make_protected_error(self, count):
        """Create a ProtectedError with 'count' fake protected objects."""
        objs = set()
        for i in range(count):
            objs.add(self._make_fake_model(i + 1))
        error = ProtectedError("Cannot delete", objs)
        return error

    def test_fewer_than_five_no_ellipsis(self):
        req = MagicMock()
        error = self._make_protected_error(3)
        with patch("application.admin.messages") as mock_msgs:
            _report_protected_error(req, error, "TestWard", 42)
        mock_msgs.error.assert_called_once()
        msg = mock_msgs.error.call_args[0][1]
        assert "TestWard" in msg
        assert "42" in msg
        assert "..." not in msg

    def test_more_than_five_has_ellipsis(self):
        req = MagicMock()
        error = self._make_protected_error(8)
        with patch("application.admin.messages") as mock_msgs:
            _report_protected_error(req, error, "TestSection", 99)
        mock_msgs.error.assert_called_once()
        msg = mock_msgs.error.call_args[0][1]
        assert "TestSection" in msg
        assert "99" in msg
        assert "..." in msg

    def test_exactly_five_no_ellipsis(self):
        req = MagicMock()
        error = self._make_protected_error(5)
        with patch("application.admin.messages") as mock_msgs:
            _report_protected_error(req, error, "Entity", 10)
        msg = mock_msgs.error.call_args[0][1]
        assert "..." not in msg


class TestDeleteDuplicateAndReport:
    """Tests for _delete_duplicate_and_report."""

    def test_successful_delete_returns_tuple(self):
        req = MagicMock()
        duplicate = MagicMock()
        duplicate.id = 7
        duplicate.delete.return_value = None

        result = _delete_duplicate_and_report(req, duplicate, lambda d: "DupName")
        assert result == ("DupName", 7)

    def test_protected_error_returns_none(self):
        req = MagicMock()
        duplicate = MagicMock()
        duplicate.id = 7

        obj = MagicMock()
        obj._meta.verbose_name = "enquiry"
        obj.pk = 1
        error = ProtectedError("Cannot delete", {obj})
        duplicate.delete.side_effect = error

        with patch("application.admin.messages"):
            result = _delete_duplicate_and_report(req, duplicate, lambda d: "DupName")
        assert result is None


class TestReassignContactsJobType:
    """Tests for _reassign_contacts_job_type."""

    @patch("application.admin.Contact")
    def test_no_contacts_returns_zero(self, mock_contact_model):
        mock_contact_model.objects.filter.return_value = []
        old_jt = MagicMock()
        new_jt = MagicMock()

        result = _reassign_contacts_job_type(old_jt, new_jt)
        assert result == 0

    @patch("application.admin.Contact")
    def test_three_contacts_returns_three(self, mock_contact_model):
        contacts = [MagicMock() for _ in range(3)]
        mock_contact_model.objects.filter.return_value = contacts
        old_jt = MagicMock()
        new_jt = MagicMock()

        result = _reassign_contacts_job_type(old_jt, new_jt)
        assert result == 3
        for contact in contacts:
            contact.job_types.remove.assert_called_once_with(old_jt)
            contact.job_types.add.assert_called_once_with(new_jt)
