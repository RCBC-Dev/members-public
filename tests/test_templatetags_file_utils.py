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
Tests for application/templatetags/file_utils.py
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from application.templatetags.file_utils import (
    file_exists,
    safe_image_url,
    display_attachment,
    attachment_status_class,
    attachment_status_text,
)


class TestFileExists:
    """Tests for file_exists filter."""

    def test_none_returns_false(self):
        assert file_exists(None) is False

    def test_empty_string_returns_false(self):
        assert file_exists("") is False

    def test_nonexistent_file_returns_false(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            assert file_exists("no_such_file.txt") is False

    def test_existing_file_returns_true(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("hello")
            assert file_exists("test.txt") is True


class TestSafeImageUrl:
    """Tests for safe_image_url filter."""

    def test_none_attachment_returns_placeholder(self):
        url = safe_image_url(None)
        assert "missing-file" in url

    def test_attachment_without_file_path_attr_returns_placeholder(self):
        url = safe_image_url("not an attachment object")
        assert "missing-file" in url

    def test_missing_jpg_returns_missing_image_placeholder(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = "photo.jpg"
            attachment.filename = "photo.jpg"
            url = safe_image_url(attachment)
            assert "missing-image" in url

    def test_missing_pdf_returns_missing_pdf_placeholder(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = "doc.pdf"
            attachment.filename = "doc.pdf"
            url = safe_image_url(attachment)
            assert "missing-pdf" in url

    def test_missing_doc_returns_missing_doc_placeholder(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = "file.docx"
            attachment.filename = "file.docx"
            url = safe_image_url(attachment)
            assert "missing-doc" in url

    def test_other_type_returns_missing_file_placeholder(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = "data.csv"
            attachment.filename = "data.csv"
            url = safe_image_url(attachment)
            assert "missing-file" in url

    def test_existing_file_returns_file_url(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            test_file = os.path.join(tmpdir, "photo.jpg")
            with open(test_file, "w") as f:
                f.write("image data")
            attachment = MagicMock()
            attachment.file_path = "photo.jpg"
            attachment.filename = "photo.jpg"
            attachment.file_url = "/media/photo.jpg"
            url = safe_image_url(attachment)
            assert url == "/media/photo.jpg"

    def test_no_file_path_returns_placeholder(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = None
            attachment.filename = "something.jpg"
            url = safe_image_url(attachment)
            assert "missing" in url


class TestDisplayAttachment:
    """Tests for display_attachment inclusion tag."""

    def test_none_attachment_returns_default_context(self):
        context = display_attachment(None)
        assert context["file_exists"] is False
        assert context["missing_file"] is True
        assert context["is_image"] is False

    def test_pdf_attachment_sets_is_pdf(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = None
            attachment.filename = "report.pdf"
            context = display_attachment(attachment)
            assert context["is_pdf"] is True

    def test_doc_attachment_sets_is_doc(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = None
            attachment.filename = "letter.docx"
            context = display_attachment(attachment)
            assert context["is_doc"] is True

    def test_jpg_attachment_sets_is_image(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = None
            attachment.filename = "photo.jpg"
            context = display_attachment(attachment)
            assert context["is_image"] is True

    def test_existing_image_sets_file_exists(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            test_file = os.path.join(tmpdir, "photo.jpg")
            with open(test_file, "w") as f:
                f.write("img")
            attachment = MagicMock()
            attachment.file_path = "photo.jpg"
            attachment.filename = "photo.jpg"
            attachment.file_url = "/media/photo.jpg"
            context = display_attachment(attachment)
            assert context["file_exists"] is True
            assert context["missing_file"] is False
            assert context["display_url"] == "/media/photo.jpg"


class TestAttachmentStatusClass:
    """Tests for attachment_status_class simple tag."""

    def test_none_returns_missing(self):
        assert attachment_status_class(None) == "attachment-missing"

    def test_string_without_file_path_attr_returns_missing(self):
        assert attachment_status_class("not an attachment") == "attachment-missing"

    def test_missing_file_returns_missing(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = "nonexistent.txt"
            assert attachment_status_class(attachment) == "attachment-missing"

    def test_existing_file_returns_available(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            test_file = os.path.join(tmpdir, "exists.txt")
            with open(test_file, "w") as f:
                f.write("data")
            attachment = MagicMock()
            attachment.file_path = "exists.txt"
            assert attachment_status_class(attachment) == "attachment-available"

    def test_none_file_path_returns_missing(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = None
            assert attachment_status_class(attachment) == "attachment-missing"


class TestAttachmentStatusText:
    """Tests for attachment_status_text simple tag."""

    def test_none_returns_not_available(self):
        assert attachment_status_text(None) == "File not available"

    def test_string_without_file_path_attr_returns_not_available(self):
        assert attachment_status_text("not an attachment") == "File not available"

    def test_missing_file_returns_not_found(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = "missing.txt"
            assert attachment_status_text(attachment) == "File not found"

    def test_existing_file_returns_available(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            test_file = os.path.join(tmpdir, "exists.txt")
            with open(test_file, "w") as f:
                f.write("data")
            attachment = MagicMock()
            attachment.file_path = "exists.txt"
            assert attachment_status_text(attachment) == "Available"

    def test_none_file_path_returns_not_found(self, settings):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings.MEDIA_ROOT = tmpdir
            attachment = MagicMock()
            attachment.file_path = None
            assert attachment_status_text(attachment) == "File not found"
