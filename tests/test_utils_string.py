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
Tests for pure-string utility functions in application/utils.py
"""

import pytest
from application.utils import (
    _format_recipient_list,
    _remove_banners,
    _remove_angle_bracket_links,
    _needs_paragraph_break,
    _is_email_header_line,
    _find_next_content_index,
    _build_paragraphs,
    _format_plain_text_for_html_display,
    strip_html_tags,
)


class TestFormatRecipientList:
    """Tests for _format_recipient_list."""

    def test_empty_string_returns_empty(self):
        assert _format_recipient_list("") == ""

    def test_none_returns_empty(self):
        assert _format_recipient_list(None) == ""

    def test_single_named_address(self):
        result = _format_recipient_list("Alice <alice@example.com>")
        assert "Alice" in result
        assert "alice@example.com" in result

    def test_bare_email_address(self):
        result = _format_recipient_list("bob@example.com")
        assert "bob@example.com" in result

    def test_multiple_recipients_semicolon_separated(self):
        result = _format_recipient_list("a@a.com; b@b.com")
        assert "a@a.com" in result
        assert "b@b.com" in result

    def test_whitespace_only_entries_are_skipped(self):
        result = _format_recipient_list("a@a.com;  ; b@b.com")
        assert result.count(";") == 1  # only one separator between two valid entries

    def test_returns_semicolon_separated_string(self):
        result = _format_recipient_list("a@a.com; b@b.com")
        assert "; " in result


class TestRemoveBanners:
    """Tests for _remove_banners."""

    def test_empty_string_returns_empty(self):
        assert _remove_banners("") == ""

    def test_none_returns_empty(self):
        assert _remove_banners(None) == ""

    def test_removes_warning_banner(self):
        text = (
            "Hello\nWARNING: This email came from outside of the organisation.\nWorld"
        )
        result = _remove_banners(text)
        assert "WARNING" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_combined_banner_line(self):
        text = "normal line\nYou don't often get email from bob@test.com. Learn why this is important\nother line"
        result = _remove_banners(text)
        assert "don't often get email" not in result
        assert "normal line" in result

    def test_preserves_regular_text(self):
        text = "Hello world\nThis is a regular email"
        result = _remove_banners(text)
        assert result == text


class TestRemoveAngleBracketLinks:
    """Tests for _remove_angle_bracket_links."""

    def test_empty_returns_empty(self):
        assert _remove_angle_bracket_links("") == ""

    def test_none_returns_empty(self):
        assert _remove_angle_bracket_links(None) == ""

    def test_removes_http_link(self):
        result = _remove_angle_bracket_links("See <http://example.com> for details")
        assert "<http://example.com>" not in result
        assert "for details" in result

    def test_removes_https_link(self):
        result = _remove_angle_bracket_links("Visit <https://example.com/path?q=1>")
        assert "<https" not in result

    def test_preserves_text_without_links(self):
        text = "No links here just plain text"
        assert _remove_angle_bracket_links(text) == text

    def test_preserves_email_addresses_in_angle_brackets(self):
        # <person@email.com> is NOT an http URL, should be preserved
        text = "Contact <person@example.com> directly"
        result = _remove_angle_bracket_links(text)
        assert "<person@example.com>" in result


class TestNeedsParagraphBreak:
    """Tests for _needs_paragraph_break."""

    def test_thanks_line_needs_break(self):
        assert _needs_paragraph_break("thanks", "John Smith") is True

    def test_regards_line_needs_break(self):
        assert _needs_paragraph_break("regards", "Next line") is True

    def test_short_line_ending_with_period_needs_break(self):
        assert _needs_paragraph_break("Done.", "Next section") is True

    def test_long_line_does_not_need_break(self):
        long_line = "This is a long line that does not need a paragraph break after it"
        assert _needs_paragraph_break(long_line, "More text") is False

    def test_short_line_before_full_name_needs_break(self):
        assert _needs_paragraph_break("Hi,", "John Smith") is True

    def test_short_line_before_team_needs_break(self):
        assert _needs_paragraph_break("Hi,", "Support Team") is True


class TestIsEmailHeaderLine:
    """Tests for _is_email_header_line."""

    def test_from_header_is_email_header(self):
        assert _is_email_header_line("From: alice@example.com") is True

    def test_case_insensitive_from(self):
        assert _is_email_header_line("from: someone@test.com") is True

    def test_regular_line_is_not_header(self):
        assert _is_email_header_line("Hello world") is False

    def test_empty_string_is_not_header(self):
        assert _is_email_header_line("") is False


class TestFindNextContentIndex:
    """Tests for _find_next_content_index."""

    def test_finds_first_non_empty_line(self):
        lines = ["", "", "hello", "world"]
        assert _find_next_content_index(lines, 0) == 2

    def test_returns_start_if_non_empty(self):
        lines = ["hello", "world"]
        assert _find_next_content_index(lines, 0) == 0

    def test_returns_len_if_all_empty(self):
        lines = ["", "", ""]
        assert _find_next_content_index(lines, 0) == 3

    def test_starts_from_given_index(self):
        lines = ["skip", "", "target"]
        assert _find_next_content_index(lines, 1) == 2


class TestBuildParagraphs:
    """Tests for _build_paragraphs."""

    def test_single_paragraph(self):
        result = _build_paragraphs(["line one", "line two"])
        assert "line one" in result
        assert "line two" in result
        assert "<br>" in result

    def test_two_paragraphs_separated_by_empty(self):
        result = _build_paragraphs(["para1", "", "para2"])
        assert "<br><br>" in result

    def test_empty_input_returns_empty_string(self):
        assert _build_paragraphs([]) == ""

    def test_all_empty_lines_returns_empty(self):
        result = _build_paragraphs(["", "", ""])
        assert result == ""


class TestFormatPlainTextForHtmlDisplay:
    """Tests for _format_plain_text_for_html_display."""

    def test_empty_returns_empty(self):
        assert _format_plain_text_for_html_display("") == ""

    def test_none_returns_empty(self):
        assert _format_plain_text_for_html_display(None) == ""

    def test_escapes_html_entities(self):
        result = _format_plain_text_for_html_display("<script>evil</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_converts_newlines_to_br(self):
        result = _format_plain_text_for_html_display("line one\nline two")
        assert "<br>" in result

    def test_normalizes_windows_line_endings(self):
        result = _format_plain_text_for_html_display("line one\r\nline two")
        assert "<br>" in result

    def test_handles_quoted_reply(self):
        # Quoted lines get HTML-escaped (> becomes &gt;) but only form a
        # styled div when they appear as a separate paragraph block
        text = "My response\n\n> Original message\n> More quoted text"
        result = _format_plain_text_for_html_display(text)
        assert "&gt;" in result  # > is escaped in the output


class TestStripHtmlTags:
    """Tests for strip_html_tags."""

    def test_strips_simple_tags(self):
        assert strip_html_tags("<p>Hello</p>") == "Hello"

    def test_strips_nested_tags(self):
        result = strip_html_tags("<div><p>Hello <b>world</b></p></div>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_empty_string_returns_empty(self):
        assert strip_html_tags("") == ""

    def test_plain_text_unchanged(self):
        assert strip_html_tags("no tags here") == "no tags here"

    def test_handles_none(self):
        result = strip_html_tags(None)
        assert result is None or result == ""
