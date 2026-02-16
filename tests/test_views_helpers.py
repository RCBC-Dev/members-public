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
Tests for pure-logic helper functions in application/views.py
"""

import pytest
from unittest.mock import MagicMock
from django.test import RequestFactory
from application.views import (
    _get_edit_success_message,
    _is_ajax,
    _get_upload_file_type,
    _build_upload_response,
    _redirect_to_referer_or_detail,
    _build_reopen_ajax_success,
    _handle_reopen_missing_reason,
    _calculate_months_back_for_dashboard,
    _compute_sla_counts,
)


class TestGetEditSuccessMessage:
    """Tests for _get_edit_success_message."""

    def _make_enquiry(self, ref="ENQ-001"):
        e = MagicMock()
        e.reference = ref
        return e

    def test_no_changes_no_attachments_returns_info(self):
        msg_type, msg = _get_edit_success_message(self._make_enquiry(), [], False)
        assert msg_type == "info"
        assert "No changes" in msg

    def test_changes_only_returns_success(self):
        msg_type, msg = _get_edit_success_message(
            self._make_enquiry(), ["title"], False
        )
        assert msg_type == "success"
        assert "updated successfully" in msg

    def test_attachments_only_returns_success(self):
        msg_type, msg = _get_edit_success_message(self._make_enquiry(), [], True)
        assert msg_type == "success"
        assert "attachments" in msg

    def test_both_changes_and_attachments(self):
        msg_type, msg = _get_edit_success_message(self._make_enquiry(), ["title"], True)
        assert msg_type == "success"
        assert "attachments" in msg

    def test_enquiry_reference_included_in_message(self):
        _, msg = _get_edit_success_message(self._make_enquiry("ENQ-999"), [], False)
        assert "ENQ-999" in msg


class TestIsAjax:
    """Tests for _is_ajax."""

    def test_returns_true_for_ajax_header(self):
        factory = RequestFactory()
        request = factory.get("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert _is_ajax(request) is True

    def test_returns_false_without_ajax_header(self):
        factory = RequestFactory()
        request = factory.get("/")
        assert _is_ajax(request) is False

    def test_returns_false_for_wrong_header_value(self):
        factory = RequestFactory()
        request = factory.get("/", HTTP_X_REQUESTED_WITH="FetchAPI")
        assert _is_ajax(request) is False


class TestGetUploadFileType:
    """Tests for _get_upload_file_type."""

    def _mock_file(self, name):
        f = MagicMock()
        f.name = name
        return f

    def test_jpg_is_image(self):
        file_type, error = _get_upload_file_type(self._mock_file("photo.jpg"))
        assert file_type == "image"
        assert error is None

    def test_png_is_image(self):
        file_type, error = _get_upload_file_type(self._mock_file("pic.png"))
        assert file_type == "image"

    def test_jpeg_is_image(self):
        file_type, error = _get_upload_file_type(self._mock_file("img.jpeg"))
        assert file_type == "image"

    def test_gif_is_image(self):
        file_type, error = _get_upload_file_type(self._mock_file("anim.gif"))
        assert file_type == "image"

    def test_pdf_is_document(self):
        file_type, error = _get_upload_file_type(self._mock_file("report.pdf"))
        assert file_type == "document"

    def test_docx_is_document(self):
        file_type, error = _get_upload_file_type(self._mock_file("letter.docx"))
        assert file_type == "document"

    def test_doc_is_document(self):
        file_type, error = _get_upload_file_type(self._mock_file("old.doc"))
        assert file_type == "document"

    def test_exe_returns_none_with_error(self):
        file_type, error = _get_upload_file_type(self._mock_file("virus.exe"))
        assert file_type is None
        assert error is not None

    def test_txt_returns_error(self):
        file_type, error = _get_upload_file_type(self._mock_file("data.txt"))
        assert file_type is None
        assert error is not None

    def test_case_insensitive_extension(self):
        file_type, error = _get_upload_file_type(self._mock_file("Photo.JPG"))
        assert file_type == "image"


class TestBuildUploadResponse:
    """Tests for _build_upload_response."""

    def _make_result(self):
        return {
            "file_path": "enquiry_photos/photo.jpg",
            "original_filename": "photo.jpg",
            "file_size": 1024,
            "file_url": "/media/enquiry_photos/photo.jpg",
            "original_size": 2048,
            "was_resized": True,
        }

    def test_basic_response_fields(self):
        result = _build_upload_response(self._make_result(), "image", True)
        assert "filename" in result
        assert "original_name" in result
        assert "size" in result
        assert "url" in result
        assert "file_type" in result

    def test_image_includes_resize_info(self):
        result = _build_upload_response(self._make_result(), "image", True)
        assert "was_resized" in result
        assert "original_size" in result

    def test_document_excludes_resize_info(self):
        doc_result = {
            "file_path": "docs/file.pdf",
            "original_filename": "file.pdf",
            "file_size": 512,
            "file_url": "/media/docs/file.pdf",
        }
        result = _build_upload_response(doc_result, "document", False)
        assert "was_resized" not in result
        assert "original_size" not in result

    def test_file_type_included(self):
        result = _build_upload_response(self._make_result(), "image", True)
        assert result["file_type"] == "image"


class TestBuildReopenAjaxSuccess:
    """Tests for _build_reopen_ajax_success."""

    def test_returns_json_response_with_success(self):
        from django.http import JsonResponse

        enquiry = MagicMock()
        enquiry.reference = "ENQ-001"
        enquiry.id = 42
        enquiry.status = "open"
        enquiry.get_status_display.return_value = "Open"
        enquiry.closed_at = None
        response = _build_reopen_ajax_success(enquiry)
        assert isinstance(response, JsonResponse)
        import json

        data = json.loads(response.content)
        assert data["success"] is True
        assert "ENQ-001" in data["message"]


class TestHandleReopenMissingReason:
    """Tests for _handle_reopen_missing_reason."""

    def test_ajax_request_returns_json(self):
        from django.http import JsonResponse

        factory = RequestFactory()
        request = factory.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        from django.contrib.messages.storage.fallback import FallbackStorage

        request.session = {}
        request._messages = FallbackStorage(request)
        response = _handle_reopen_missing_reason(request, 1)
        assert isinstance(response, JsonResponse)


class TestCalculateMonthsBackForDashboard:
    """Tests for _calculate_months_back_for_dashboard."""

    def test_non_custom_non_all_uses_date_range_months(self):
        date_range_info = MagicMock()
        date_range_info.months = 6
        months_back, _ = _calculate_months_back_for_dashboard(
            "6months", date_range_info, MagicMock()
        )
        assert months_back == 6

    def test_none_months_defaults_to_12(self):
        date_range_info = MagicMock()
        date_range_info.months = None
        months_back, _ = _calculate_months_back_for_dashboard(
            "3months", date_range_info, MagicMock()
        )
        assert months_back == 12


class TestComputeSlaCounts:
    """Tests for _compute_sla_counts."""

    def test_empty_list_returns_zeros(self):
        within, outside = _compute_sla_counts([])
        assert within == 0
        assert outside == 0

    def test_enquiry_without_dates_is_skipped(self):
        enquiry = MagicMock()
        enquiry.created_at = None
        enquiry.closed_at = None
        within, outside = _compute_sla_counts([enquiry])
        assert within == 0
        assert outside == 0
