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
Tests for EnquiryService change tracking and history methods in application/services.py
"""

import pytest
from unittest.mock import MagicMock, patch
from application.services import EnquiryService


class TestHasFieldChanged:
    """Tests for EnquiryService._has_field_changed."""

    def test_simple_no_change(self):
        assert (
            EnquiryService._has_field_changed("title", "simple", "foo", "foo") is False
        )

    def test_simple_changed(self):
        assert (
            EnquiryService._has_field_changed("title", "simple", "foo", "bar") is True
        )

    def test_simple_none_to_value(self):
        assert EnquiryService._has_field_changed("title", "simple", None, "bar") is True

    def test_fk_delegates_to_compare_foreign_key(self):
        old = MagicMock()
        old.id = 1
        new = MagicMock()
        new.id = 2
        assert EnquiryService._has_field_changed("member", "fk", old, new) is True

    def test_fk_same(self):
        old = MagicMock()
        old.id = 1
        new = MagicMock()
        new.id = 1
        assert EnquiryService._has_field_changed("member", "fk", old, new) is False

    def test_description_delegates(self):
        assert (
            EnquiryService._has_field_changed(
                "description", "description", "<p>Hello</p>", "<p>Hello</p>"
            )
            is False
        )

    def test_description_changed(self):
        assert (
            EnquiryService._has_field_changed(
                "description", "description", "<p>Hello</p>", "<p>Goodbye</p>"
            )
            is True
        )


class TestCompareDescription:
    """Tests for EnquiryService._compare_description."""

    def test_both_empty(self):
        assert EnquiryService._compare_description("", "") is False

    def test_both_none(self):
        assert EnquiryService._compare_description(None, None) is False

    def test_same_html_content(self):
        assert (
            EnquiryService._compare_description("<p>Hello</p>", "<p>Hello</p>") is False
        )

    def test_different_html_same_text(self):
        # Same text, different tags - should be False (text is the same)
        assert (
            EnquiryService._compare_description("<p>Hello</p>", "<div>Hello</div>")
            is False
        )

    def test_different_text(self):
        assert (
            EnquiryService._compare_description("<p>Hello</p>", "<p>World</p>") is True
        )

    def test_empty_tags_vs_empty(self):
        # Both have empty text after stripping
        assert EnquiryService._compare_description("<p></p>", "") is False

    def test_non_string_comparison(self):
        # Non-string types fall through to direct comparison
        assert EnquiryService._compare_description(123, 456) is True
        assert EnquiryService._compare_description(123, 123) is False


class TestCompareForeignKey:
    """Tests for EnquiryService._compare_foreign_key."""

    def test_same_model_instances(self):
        old = MagicMock()
        old.id = 5
        new = MagicMock()
        new.id = 5
        assert EnquiryService._compare_foreign_key(old, new) is False

    def test_different_model_instances(self):
        old = MagicMock()
        old.id = 5
        new = MagicMock()
        new.id = 10
        assert EnquiryService._compare_foreign_key(old, new) is True

    def test_old_none_new_instance(self):
        new = MagicMock()
        new.id = 5
        assert EnquiryService._compare_foreign_key(None, new) is True

    def test_old_instance_new_none(self):
        old = MagicMock()
        old.id = 5
        assert EnquiryService._compare_foreign_key(old, None) is True

    def test_both_none(self):
        assert EnquiryService._compare_foreign_key(None, None) is False

    def test_new_is_integer_id(self):
        old = MagicMock()
        old.id = 5
        assert EnquiryService._compare_foreign_key(old, 5) is False

    def test_new_is_different_integer_id(self):
        old = MagicMock()
        old.id = 5
        assert EnquiryService._compare_foreign_key(old, 10) is True

    def test_new_is_string_id(self):
        old = MagicMock()
        old.id = 5
        assert EnquiryService._compare_foreign_key(old, "5") is False

    def test_new_is_empty_string(self):
        old = MagicMock()
        old.id = 5
        assert EnquiryService._compare_foreign_key(old, "") is True


class TestFormatFieldValue:
    """Tests for EnquiryService._format_field_value."""

    def test_none_value(self):
        assert EnquiryService._format_field_value("title", None) == "None"

    def test_empty_string(self):
        assert EnquiryService._format_field_value("title", "") == "None"

    def test_regular_value(self):
        assert EnquiryService._format_field_value("title", "My Title") == "My Title"

    def test_description_strips_html(self):
        result = EnquiryService._format_field_value(
            "description", "<p>Hello <b>World</b></p>"
        )
        assert "<p>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_model_object_uses_str(self):
        obj = MagicMock()
        obj.__str__ = lambda self: "Mock Object"
        result = EnquiryService._format_field_value("member", obj)
        assert "Mock" in result


class TestBuildChangeDict:
    """Tests for EnquiryService._build_change_dict."""

    def test_simple_field(self):
        result = EnquiryService._build_change_dict("title", "Title", "Old", "New")
        assert result["field_name"] == "title"
        assert result["display_name"] == "Title"
        assert result["old_value"] == "Old"
        assert result["new_value"] == "New"
        assert "old_value_raw" not in result

    def test_description_field_includes_raw(self):
        result = EnquiryService._build_change_dict(
            "description", "Description", "<p>Old</p>", "<p>New</p>"
        )
        assert result["field_name"] == "description"
        assert "old_value_raw" in result
        assert result["old_value_raw"] == "<p>Old</p>"
        assert result["new_value_raw"] == "<p>New</p>"

    def test_none_values(self):
        result = EnquiryService._build_change_dict("title", "Title", None, "New")
        assert result["old_value"] == "None"
        assert result["new_value"] == "New"


class TestTrackEnquiryChanges:
    """Tests for EnquiryService.track_enquiry_changes."""

    def test_no_changes(self):
        enquiry = MagicMock()
        enquiry.title = "Test"
        enquiry.description = "<p>Desc</p>"
        enquiry.member = MagicMock(id=1)
        enquiry.contact = MagicMock(id=2)
        enquiry.section = MagicMock(id=3)
        enquiry.job_type = MagicMock(id=4)

        new_data = {
            "title": "Test",
            "description": "<p>Desc</p>",
            "member": MagicMock(id=1),
            "contact": MagicMock(id=2),
            "section": MagicMock(id=3),
            "job_type": MagicMock(id=4),
        }

        changes = EnquiryService.track_enquiry_changes(enquiry, new_data)
        assert changes == []

    def test_title_changed(self):
        enquiry = MagicMock()
        enquiry.title = "Old Title"
        new_data = {"title": "New Title"}

        changes = EnquiryService.track_enquiry_changes(enquiry, new_data)
        assert len(changes) == 1
        assert changes[0]["field_name"] == "title"
        assert changes[0]["old_value"] == "Old Title"
        assert changes[0]["new_value"] == "New Title"

    def test_field_not_in_new_data_skipped(self):
        enquiry = MagicMock()
        enquiry.title = "Test"
        # new_data doesn't contain title
        changes = EnquiryService.track_enquiry_changes(enquiry, {})
        assert changes == []

    def test_multiple_changes(self):
        enquiry = MagicMock()
        enquiry.title = "Old"
        enquiry.member = MagicMock(id=1)

        new_data = {
            "title": "New",
            "member": MagicMock(id=2),
        }

        changes = EnquiryService.track_enquiry_changes(enquiry, new_data)
        assert len(changes) == 2
        field_names = [c["field_name"] for c in changes]
        assert "title" in field_names
        assert "member" in field_names


class TestCreateAttachmentHistoryMessages:
    """Tests for EnquiryService._create_attachment_history_messages."""

    @patch("application.services.EnquiryHistory")
    def test_zero_total_creates_no_history(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {"email": 0, "manual": 0, "total": 0, "filenames": []}

        EnquiryService._create_attachment_history_messages(counts, enquiry, user)
        mock_history.objects.create.assert_not_called()

    @patch("application.services.EnquiryHistory")
    def test_email_only(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {"email": 2, "manual": 0, "total": 2, "filenames": ["a.jpg", "b.jpg"]}

        EnquiryService._create_attachment_history_messages(counts, enquiry, user)
        mock_history.objects.create.assert_called_once()
        note = mock_history.objects.create.call_args[1]["note"]
        assert "2 file(s) from email" in note
        assert "a.jpg" in note

    @patch("application.services.EnquiryHistory")
    def test_manual_only(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {"email": 0, "manual": 3, "total": 3, "filenames": ["doc.pdf"]}

        EnquiryService._create_attachment_history_messages(counts, enquiry, user)
        note = mock_history.objects.create.call_args[1]["note"]
        assert "3 file(s) manually attached" in note

    @patch("application.services.EnquiryHistory")
    def test_mixed_attachments(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {
            "email": 1,
            "manual": 2,
            "total": 3,
            "filenames": ["a.jpg", "b.pdf", "c.png"],
        }

        EnquiryService._create_attachment_history_messages(counts, enquiry, user)
        note = mock_history.objects.create.call_args[1]["note"]
        assert "1 file(s) from email" in note
        assert "2 manually attached" in note


class TestCreateCombinedCreationHistoryEntry:
    """Tests for EnquiryService._create_combined_creation_history_entry."""

    @patch("application.services.EnquiryHistory")
    def test_no_attachments(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {"email": 0, "manual": 0, "total": 0, "filenames": []}

        EnquiryService._create_combined_creation_history_entry(enquiry, user, counts)
        note = mock_history.objects.create.call_args[1]["note"]
        assert note == "Enquiry created"

    @patch("application.services.EnquiryHistory")
    def test_email_attachments(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {"email": 2, "manual": 0, "total": 2, "filenames": ["a.jpg", "b.png"]}

        EnquiryService._create_combined_creation_history_entry(enquiry, user, counts)
        note = mock_history.objects.create.call_args[1]["note"]
        assert "Enquiry created with 2 file(s) from email" in note
        assert "a.jpg, b.png" in note

    @patch("application.services.EnquiryHistory")
    def test_manual_attachments(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {"email": 0, "manual": 1, "total": 1, "filenames": ["doc.pdf"]}

        EnquiryService._create_combined_creation_history_entry(enquiry, user, counts)
        note = mock_history.objects.create.call_args[1]["note"]
        assert "1 manually attached file(s)" in note

    @patch("application.services.EnquiryHistory")
    def test_mixed_attachments(self, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        counts = {"email": 1, "manual": 1, "total": 2, "filenames": ["a.jpg", "b.pdf"]}

        EnquiryService._create_combined_creation_history_entry(enquiry, user, counts)
        note = mock_history.objects.create.call_args[1]["note"]
        assert "1 file(s) from email" in note
        assert "1 manually attached" in note


class TestCreateFieldChangeHistoryEntries:
    """Tests for EnquiryService.create_field_change_history_entries."""

    @patch("application.services.EnquiryHistory")
    @patch("application.services.get_text_diff", return_value=None)
    def test_single_simple_change(self, mock_diff, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        changes = [
            {
                "field_name": "title",
                "display_name": "Title",
                "old_value": "Old",
                "new_value": "New",
            }
        ]

        EnquiryService.create_field_change_history_entries(enquiry, changes, user)
        mock_history.objects.create.assert_called_once()
        note = mock_history.objects.create.call_args[1]["note"]
        assert "Title changed from 'Old' to 'New'" in note

    @patch("application.services.EnquiryHistory")
    @patch("application.services.get_text_diff", return_value="added 'World'")
    def test_single_description_change(self, mock_diff, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        changes = [
            {
                "field_name": "description",
                "display_name": "Description",
                "old_value": "Hello",
                "new_value": "Hello World",
                "old_value_raw": "<p>Hello</p>",
                "new_value_raw": "<p>Hello World</p>",
            }
        ]

        EnquiryService.create_field_change_history_entries(enquiry, changes, user)
        note = mock_history.objects.create.call_args[1]["note"]
        assert "Description updated" in note

    @patch("application.services.EnquiryHistory")
    @patch("application.services.get_text_diff", return_value=None)
    def test_multiple_changes(self, mock_diff, mock_history):
        enquiry = MagicMock()
        user = MagicMock()
        changes = [
            {
                "field_name": "title",
                "display_name": "Title",
                "old_value": "Old",
                "new_value": "New",
            },
            {
                "field_name": "description",
                "display_name": "Description",
                "old_value": "Old desc",
                "new_value": "New desc",
                "old_value_raw": "Old desc",
                "new_value_raw": "New desc",
            },
        ]

        EnquiryService.create_field_change_history_entries(enquiry, changes, user)
        note = mock_history.objects.create.call_args[1]["note"]
        assert "Multiple fields updated" in note
        assert "Title:" in note
