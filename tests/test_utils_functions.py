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
Tests for additional utility functions in application/utils.py
"""

import io
import os
import pytest
from unittest.mock import MagicMock, patch
from django.http import JsonResponse
from application.utils import (
    safe_file_path_join,
    get_text_diff,
    create_json_response,
    _extract_file_info,
    _get_attachment_filename,
    _process_snippet_body,
    _process_plain_body,
    _detect_email_direction,
    _insert_reply_separators,
    clear_all_session_cache,
    validate_file_security,
    _build_paragraphs,
    _needs_paragraph_break,
    _is_email_header_line,
    _find_next_content_index,
    _process_lines_with_spacing,
    _format_recipient_list,
    _parse_sender_info,
    _remove_banners,
    _remove_angle_bracket_links,
)


class TestSafeFilePathJoin:
    """Tests for safe_file_path_join."""

    def test_basic_join(self):
        result = safe_file_path_join("/media", "photos/file.jpg")
        assert "media" in result
        assert "photos" in result
        assert "file.jpg" in result

    def test_raises_for_no_paths(self):
        with pytest.raises((ValueError, TypeError)):
            safe_file_path_join()

    def test_raises_for_null_byte(self):
        with pytest.raises(ValueError, match="Null byte"):
            safe_file_path_join("/media", "file\x00name.jpg")

    def test_raises_for_directory_traversal(self):
        # Use a relative base so normpath preserves '..' components
        with pytest.raises(ValueError, match="traversal"):
            safe_file_path_join("relative_base", "../../../etc/passwd")

    def test_raises_for_pipe_in_path(self):
        with pytest.raises(ValueError):
            safe_file_path_join("/media", "file|cmd.jpg")

    def test_raises_for_semicolon_in_path(self):
        with pytest.raises(ValueError):
            safe_file_path_join("/media", "file;cmd.jpg")

    def test_raises_for_absolute_second_component(self):
        # Use a Windows-style absolute path for the second component
        with pytest.raises(ValueError, match="Absolute"):
            safe_file_path_join("/media", "C:/Windows/system32")

    def test_allows_normal_relative_paths(self):
        result = safe_file_path_join("/media", "enquiry_photos/2024/01/photo.jpg")
        assert "enquiry_photos" in result


class TestGetTextDiff:
    """Tests for get_text_diff."""

    def test_identical_texts_returns_none(self):
        assert get_text_diff("hello world", "hello world") is None

    def test_none_old_text_treated_as_empty(self):
        result = get_text_diff(None, "new text")
        assert result is not None

    def test_none_new_text_treated_as_empty(self):
        result = get_text_diff("old text", None)
        assert result is not None

    def test_both_none_returns_none(self):
        # Both empty = identical = None
        assert get_text_diff(None, None) is None

    def test_detects_added_words(self):
        result = get_text_diff("hello", "hello world")
        assert result is not None
        assert "Added" in result

    def test_detects_removed_words(self):
        result = get_text_diff("hello world", "hello")
        assert result is not None
        assert "Removed" in result

    def test_strips_html_before_comparison(self):
        result = get_text_diff("<p>hello</p>", "<p>hello</p>")
        assert result is None  # Same text after stripping

    def test_truncates_long_changes(self):
        long_text = "word " * 200
        result = get_text_diff("", long_text)
        assert result is not None
        assert "..." in result


class TestCreateJsonResponse:
    """Tests for create_json_response."""

    def test_success_response(self):
        response = create_json_response(True)
        import json
        data = json.loads(response.content)
        assert data["success"] is True

    def test_error_response(self):
        response = create_json_response(False, error="Something failed")
        import json
        data = json.loads(response.content)
        assert data["success"] is False
        assert data["error"] == "Something failed"

    def test_default_error_message(self):
        response = create_json_response(False)
        import json
        data = json.loads(response.content)
        assert "error" in data

    def test_success_with_message(self):
        response = create_json_response(True, message="Done!")
        import json
        data = json.loads(response.content)
        assert data["message"] == "Done!"
        assert data["message_type"] == "success"

    def test_success_with_dict_data(self):
        response = create_json_response(True, data={"id": 42})
        import json
        data = json.loads(response.content)
        assert data["id"] == 42

    def test_success_with_list_data(self):
        response = create_json_response(True, data=[1, 2, 3])
        import json
        data = json.loads(response.content)
        assert data["data"] == [1, 2, 3]

    def test_success_with_extra_kwargs(self):
        response = create_json_response(True, count=10)
        import json
        data = json.loads(response.content)
        assert data["count"] == 10

    def test_returns_json_response_object(self):
        response = create_json_response(True)
        assert isinstance(response, JsonResponse)

    def test_error_has_message_type_error(self):
        response = create_json_response(False, error="fail")
        import json
        data = json.loads(response.content)
        assert data["message_type"] == "error"


class TestExtractFileInfo:
    """Tests for _extract_file_info."""

    def test_bytes_input_returns_length(self):
        data = b"hello world"
        size, name = _extract_file_info(data)
        assert size == len(data)
        assert name == "uploaded_file"

    def test_file_like_with_size_attribute(self):
        f = MagicMock()
        f.size = 1024
        f.name = "test.jpg"
        f.read = MagicMock(return_value=b"")
        size, name = _extract_file_info(f)
        assert size == 1024
        assert name == "test.jpg"

    def test_file_like_without_size_uses_read(self):
        f = io.BytesIO(b"file content here")
        size, name = _extract_file_info(f)
        assert size == len(b"file content here")


class TestGetAttachmentFilename:
    """Tests for _get_attachment_filename."""

    def test_returns_long_filename_if_available(self):
        attachment = MagicMock()
        attachment.longFilename = "document.pdf"
        attachment.shortFilename = "doc.pdf"
        assert _get_attachment_filename(attachment) == "document.pdf"

    def test_falls_back_to_short_filename(self):
        attachment = MagicMock()
        attachment.longFilename = None
        attachment.shortFilename = "doc.pdf"
        assert _get_attachment_filename(attachment) == "doc.pdf"


class TestProcessSnippetBody:
    """Tests for _process_snippet_body."""

    def test_short_text_not_truncated(self):
        body, is_html = _process_snippet_body("Hello world")
        assert "Hello" in body
        assert is_html is False

    def test_long_text_truncated(self):
        long_text = "word " * 100
        body, is_html = _process_snippet_body(long_text)
        assert len(body) <= 260  # Roughly 250 + "..."
        assert is_html is False

    def test_removes_banners(self):
        text = "WARNING: This email came from outside of the organisation. Do not provide login or password details. Always be cautious opening links and attachments wherever the email appears to come from. If you have any doubts about this email, contact ICT.\n\nHello"
        body, _ = _process_snippet_body(text)
        assert "WARNING" not in body
        assert "Hello" in body

    def test_empty_body(self):
        body, is_html = _process_snippet_body("")
        assert is_html is False


class TestProcessPlainBody:
    """Tests for _process_plain_body."""

    def test_returns_cleaned_text(self):
        body, is_html = _process_plain_body("Hello world")
        assert "Hello world" in body
        assert is_html is False

    def test_normalizes_line_endings(self):
        body, _ = _process_plain_body("line1\r\nline2")
        assert "\r\n" not in body

    def test_removes_banners(self):
        text = "WARNING: This email came from outside of the organisation. Do not provide login or password details. Always be cautious opening links and attachments wherever the email appears to come from. If you have any doubts about this email, contact ICT.\n\nMain content"
        body, _ = _process_plain_body(text)
        assert "WARNING" not in body
        assert "Main content" in body


class TestDetectEmailDirection:
    """Tests for _detect_email_direction."""

    def test_incoming_when_to_field_has_target(self):
        msg = MagicMock()
        msg.to = "memberenquiries@redcar-cleveland.gov.uk"
        msg.cc = None
        msg.bcc = None
        direction = _detect_email_direction(msg, "normal body")
        assert direction == "INCOMING"

    def test_incoming_when_cc_has_target(self):
        msg = MagicMock()
        msg.to = "other@example.com"
        msg.cc = "memberenquiries@redcar-cleveland.gov.uk"
        direction = _detect_email_direction(msg, "normal body")
        assert direction == "INCOMING"

    def test_incoming_when_has_warning_banner(self):
        msg = MagicMock()
        msg.to = "other@example.com"
        msg.cc = None
        msg.bcc = None
        body = "WARNING: This email came from outside of the organisation. Do not provide login or password details. Always be cautious opening links and attachments wherever the email appears to come from. If you have any doubts about this email, contact ICT.\n\nHello"
        direction = _detect_email_direction(msg, body)
        assert direction == "INCOMING"

    def test_outgoing_when_no_target_and_no_banner(self):
        msg = MagicMock()
        msg.to = "other@example.com"
        msg.cc = None
        msg.bcc = None
        direction = _detect_email_direction(msg, "Regular email content")
        assert direction == "OUTGOING"


class TestInsertReplySeparators:
    """Tests for _insert_reply_separators."""

    def test_passthrough_for_simple_lines(self):
        lines = ["line one", "line two"]
        result = _insert_reply_separators(lines)
        assert result == lines

    def test_inserts_hr_before_from_header(self):
        # Needs i > 2 so the From: header must be at index 3+
        lines = ["line 1", "line 2", "line 3", "", "From: sender@example.com"]
        result = _insert_reply_separators(lines)
        assert "<hr>" in result

    def test_inserts_hr_before_dash_separator(self):
        # Needs i > 2 so the dash line must be at index 3+
        lines = ["line 1", "line 2", "line 3", "", "----------"]
        result = _insert_reply_separators(lines)
        assert "<hr>" in result

    def test_no_hr_at_start_of_content(self):
        lines = ["From: sender@example.com"]
        result = _insert_reply_separators(lines)
        # No hr before first line (needs >2 lines before it)
        assert "<hr>" not in result


class TestClearAllSessionCache:
    """Tests for clear_all_session_cache."""

    def test_clears_merge_confirm_keys(self):
        request = MagicMock()
        request.session = {
            "merge_confirm_1": "data1",
            "merge_confirm_2": "data2",
            "other_key": "keep",
        }
        clear_all_session_cache(request)
        assert "merge_confirm_1" not in request.session
        assert "merge_confirm_2" not in request.session
        assert "other_key" in request.session

    def test_empty_session_does_nothing(self):
        request = MagicMock()
        request.session = {}
        clear_all_session_cache(request)
        assert request.session == {}
