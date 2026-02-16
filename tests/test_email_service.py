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
Tests for application/email_service.py
"""

import pytest
from unittest.mock import MagicMock, patch
from application.email_service import EmailProcessingService


class TestValidateEmailFile:
    """Tests for EmailProcessingService.validate_email_file."""

    def test_none_file_returns_error(self):
        result = EmailProcessingService.validate_email_file(None)
        assert result["success"] is False
        assert result["error_type"] == "missing_file"

    def test_unsupported_extension_returns_error(self):
        mock_file = MagicMock()
        mock_file.name = "document.pdf"
        result = EmailProcessingService.validate_email_file(mock_file)
        assert result["success"] is False
        assert result["error_type"] == "invalid_extension"

    def test_txt_extension_returns_error(self):
        mock_file = MagicMock()
        mock_file.name = "email.txt"
        result = EmailProcessingService.validate_email_file(mock_file)
        assert result["success"] is False
        assert result["error_type"] == "invalid_extension"

    def test_msg_extension_passes_to_security_service(self):
        mock_file = MagicMock()
        mock_file.name = "email.msg"
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            result = EmailProcessingService.validate_email_file(mock_file)
            assert result["success"] is True
            mock_upload.assert_called_once_with(mock_file)

    def test_eml_extension_passes_to_security_service(self):
        mock_file = MagicMock()
        mock_file.name = "email.eml"
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            result = EmailProcessingService.validate_email_file(mock_file)
            assert result["success"] is True

    def test_security_service_failure_propagates(self):
        mock_file = MagicMock()
        mock_file.name = "email.msg"
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {
                "success": False,
                "error": "File too large",
                "error_type": "size_limit",
            }
            result = EmailProcessingService.validate_email_file(mock_file)
            assert result["success"] is False
            assert result["error"] == "File too large"

    def test_security_service_exception_returns_error(self):
        mock_file = MagicMock()
        mock_file.name = "email.msg"
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.side_effect = Exception("unexpected error")
            result = EmailProcessingService.validate_email_file(mock_file)
            assert result["success"] is False
            assert result["error_type"] == "processing"

    def test_case_insensitive_extension(self):
        mock_file = MagicMock()
        mock_file.name = "email.MSG"
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            result = EmailProcessingService.validate_email_file(mock_file)
            assert result["success"] is True


class TestExtractSenderEmail:
    """Tests for EmailProcessingService.extract_sender_email."""

    def test_none_email_data_returns_empty(self):
        email, success = EmailProcessingService.extract_sender_email(None)
        assert email == ""
        assert success is False

    def test_empty_dict_returns_empty(self):
        email, success = EmailProcessingService.extract_sender_email({})
        assert email == ""
        assert success is False

    def test_non_dict_returns_empty(self):
        email, success = EmailProcessingService.extract_sender_email("not a dict")
        assert email == ""
        assert success is False

    def test_extracts_from_email_from_field(self):
        email, success = EmailProcessingService.extract_sender_email(
            {"email_from": "Alice <alice@example.com>"}
        )
        assert success is True
        assert email == "alice@example.com"

    def test_extracts_bare_email_from_email_from(self):
        email, success = EmailProcessingService.extract_sender_email(
            {"email_from": "bob@example.com"}
        )
        assert success is True
        assert email == "bob@example.com"

    def test_falls_back_to_raw_from(self):
        email, success = EmailProcessingService.extract_sender_email(
            {"raw_from": "Carol <carol@example.com>"}
        )
        assert success is True
        assert email == "carol@example.com"

    def test_email_from_takes_priority_over_raw_from(self):
        email, success = EmailProcessingService.extract_sender_email(
            {
                "email_from": "primary@example.com",
                "raw_from": "fallback@example.com",
            }
        )
        assert success is True
        assert email == "primary@example.com"

    def test_empty_email_from_falls_back_to_raw_from(self):
        email, success = EmailProcessingService.extract_sender_email(
            {"email_from": "", "raw_from": "dave@example.com"}
        )
        assert success is True
        assert email == "dave@example.com"

    def test_both_empty_returns_empty(self):
        email, success = EmailProcessingService.extract_sender_email(
            {"email_from": "", "raw_from": ""}
        )
        assert email == ""
        assert success is False


@pytest.mark.django_db
class TestFindMemberByEmail:
    """Tests for EmailProcessingService.find_member_by_email."""

    def test_none_email_returns_none(self):
        result = EmailProcessingService.find_member_by_email(None)
        assert result is None

    def test_empty_email_returns_none(self):
        result = EmailProcessingService.find_member_by_email("")
        assert result is None

    def test_nonexistent_email_returns_none(self):
        result = EmailProcessingService.find_member_by_email("nobody@example.com")
        assert result is None


class TestParsingModes:
    """Tests for EmailProcessingService parsing modes constant."""

    def test_snippet_mode_defined(self):
        assert "snippet" in EmailProcessingService.PARSING_MODES

    def test_full_mode_defined(self):
        assert "full" in EmailProcessingService.PARSING_MODES

    def test_plain_mode_defined(self):
        assert "plain" in EmailProcessingService.PARSING_MODES


class TestParseEmailFile:
    """Tests for EmailProcessingService.parse_email_file."""

    def _make_file(self, name="email.msg", chunks=None):
        f = MagicMock()
        f.name = name
        f.chunks.return_value = iter(chunks or [b"MSG data"])
        return f

    def test_invalid_file_returns_error(self):
        """Validation failure short-circuits to error."""
        result = EmailProcessingService.parse_email_file(None)
        assert result["success"] is False

    def test_eml_not_implemented_returns_error(self):
        f = self._make_file(name="email.eml")
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            result = EmailProcessingService.parse_email_file(f)
        assert result["success"] is False
        assert "not_implemented" in result.get("error_type", "")

    def test_invalid_parsing_mode_falls_back_to_snippet(self):
        f = self._make_file()
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            with patch("application.email_service.parse_msg_file") as mock_parse:
                mock_parse.return_value = {"email_from": "a@b.com", "subject": "Test"}
                result = EmailProcessingService.parse_email_file(
                    f, parsing_mode="invalid_mode"
                )
        # Invalid mode falls back to snippet
        assert result["success"] is True
        assert result["parsing_mode"] == "snippet"

    def test_msg_parsed_successfully(self):
        f = self._make_file()
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            with patch("application.email_service.parse_msg_file") as mock_parse:
                mock_parse.return_value = {"email_from": "a@b.com", "subject": "Test"}
                result = EmailProcessingService.parse_email_file(
                    f, parsing_mode="snippet"
                )
        assert result["success"] is True
        assert "email_data" in result

    def test_parse_error_in_result_propagates(self):
        f = self._make_file()
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            with patch("application.email_service.parse_msg_file") as mock_parse:
                mock_parse.return_value = {"error": "Parsing failed"}
                result = EmailProcessingService.parse_email_file(f)
        assert result["success"] is False
        assert result["error_type"] == "parsing_error"

    def test_exception_during_processing_returns_error(self):
        f = self._make_file()
        with patch(
            "application.email_service.FileUploadService.handle_email_upload"
        ) as mock_upload:
            mock_upload.return_value = {"success": True, "file_info": {}}
            with patch(
                "application.email_service.parse_msg_file",
                side_effect=Exception("boom"),
            ):
                result = EmailProcessingService.parse_email_file(f)
        assert result["success"] is False
        assert result["error_type"] == "processing"


class TestProcessEmailForFormPopulation:
    """Tests for EmailProcessingService.process_email_for_form_population."""

    def _make_file(self, name="email.msg"):
        f = MagicMock()
        f.name = name
        f.chunks.return_value = iter([b"MSG data"])
        return f

    def test_parse_failure_returns_json_error(self):
        from django.http import JsonResponse

        f = self._make_file()
        with patch.object(EmailProcessingService, "parse_email_file") as mock_parse:
            mock_parse.return_value = {"success": False, "error": "bad file"}
            response = EmailProcessingService.process_email_for_form_population(f)
        assert isinstance(response, JsonResponse)
        import json

        data = json.loads(response.content)
        assert data["success"] is False

    def test_no_sender_returns_json_error(self):
        from django.http import JsonResponse

        f = self._make_file()
        with patch.object(EmailProcessingService, "parse_email_file") as mock_parse:
            mock_parse.return_value = {
                "success": True,
                "email_data": {"email_from": ""},
            }
            with patch.object(
                EmailProcessingService, "extract_sender_email"
            ) as mock_extract:
                mock_extract.return_value = ("", False)
                response = EmailProcessingService.process_email_for_form_population(f)
        import json

        data = json.loads(response.content)
        assert data["success"] is False

    def test_success_without_member(self):
        from django.http import JsonResponse

        f = self._make_file()
        email_data = {
            "email_from": "test@example.com",
            "subject": "Test",
            "body_content": "Hello",
            "email_to": "to@example.com",
            "email_cc": "",
            "email_date_str": "Jan 01, 2024",
            "image_attachments": [],
        }
        with patch.object(EmailProcessingService, "parse_email_file") as mock_parse:
            mock_parse.return_value = {"success": True, "email_data": email_data}
            with patch.object(
                EmailProcessingService, "extract_sender_email"
            ) as mock_extract:
                mock_extract.return_value = ("test@example.com", True)
                with patch.object(
                    EmailProcessingService, "find_member_by_email"
                ) as mock_member:
                    mock_member.return_value = None
                    response = EmailProcessingService.process_email_for_form_population(
                        f
                    )
        import json

        data = json.loads(response.content)
        assert data["success"] is True
        assert data["member_found"] is False

    def test_success_with_member(self):
        from django.http import JsonResponse

        f = self._make_file()
        email_data = {
            "email_from": "member@example.com",
            "subject": "Test",
            "body_content": "Hello",
            "email_to": "",
            "email_cc": "",
            "email_date_str": "",
            "image_attachments": [],
        }
        mock_member = MagicMock()
        mock_member.id = 1
        mock_member.full_name = "John Smith"
        mock_member.email = "member@example.com"
        mock_member.ward.name = "Test Ward"

        with patch.object(EmailProcessingService, "parse_email_file") as mock_parse:
            mock_parse.return_value = {"success": True, "email_data": email_data}
            with patch.object(
                EmailProcessingService, "extract_sender_email"
            ) as mock_extract:
                mock_extract.return_value = ("member@example.com", True)
                with patch.object(
                    EmailProcessingService, "find_member_by_email"
                ) as mock_find:
                    mock_find.return_value = mock_member
                    response = EmailProcessingService.process_email_for_form_population(
                        f
                    )
        import json

        data = json.loads(response.content)
        assert data["success"] is True
        assert data["member_found"] is True
        assert "member_info" in data

    def test_conversation_mode_defined(self):
        assert "conversation" in EmailProcessingService.PARSING_MODES

    def test_supported_extensions_include_msg(self):
        assert ".msg" in EmailProcessingService.SUPPORTED_EXTENSIONS

    def test_supported_extensions_include_eml(self):
        assert ".eml" in EmailProcessingService.SUPPORTED_EXTENSIONS
