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
Tests for application/templatetags/custom_filters.py
"""

import pytest
from application.templatetags.custom_filters import (
    get_by_key,
    list_index,
    month_last_day,
    replace_nbsp,
    smart_linebreaks,
)


class TestGetByKey:
    """Tests for the get_by_key filter."""

    def test_gets_value_from_dict(self):
        assert get_by_key({"a": 42}, "a") == 42

    def test_returns_zero_for_missing_dict_key(self):
        assert get_by_key({"a": 1}, "missing") == 0

    def test_gets_attribute_from_object(self):
        class Obj:
            score = 99

        assert get_by_key(Obj(), "score") == 99

    def test_returns_zero_for_missing_object_attribute(self):
        class Obj:
            pass

        assert get_by_key(Obj(), "nope") == 0


class TestListIndex:
    """Tests for the list_index filter."""

    def test_returns_item_at_valid_index(self):
        assert list_index(["a", "b", "c"], 1) == "b"

    def test_returns_empty_string_for_out_of_range(self):
        assert list_index([1, 2], 10) == ""

    def test_returns_empty_string_for_non_numeric_arg(self):
        assert list_index([1, 2, 3], "bad") == ""

    def test_returns_empty_string_for_none_arg(self):
        assert list_index([1, 2, 3], None) == ""

    def test_works_with_string_numeric_arg(self):
        assert list_index(["x", "y", "z"], "2") == "z"


class TestMonthLastDay:
    """Tests for the month_last_day filter."""

    def test_returns_last_day_of_january(self):
        assert month_last_day("2024-01") == "2024-01-31"

    def test_returns_last_day_of_december(self):
        assert month_last_day("2024-12") == "2024-12-31"

    def test_returns_last_day_of_february_leap_year(self):
        assert month_last_day("2024-02") == "2024-02-29"

    def test_returns_last_day_of_february_non_leap_year(self):
        assert month_last_day("2023-02") == "2023-02-28"

    def test_returns_last_day_of_april(self):
        assert month_last_day("2024-04") == "2024-04-30"

    def test_returns_original_value_for_invalid_format(self):
        assert month_last_day("not-a-date") == "not-a-date"

    def test_returns_original_value_for_empty_string(self):
        assert month_last_day("") == ""


class TestReplaceNbsp:
    """Tests for the replace_nbsp filter."""

    def test_replaces_unicode_nbsp(self):
        assert replace_nbsp("hello\u00a0world") == "hello world"

    def test_replaces_html_entity_nbsp(self):
        assert replace_nbsp("hello&nbsp;world") == "hello world"

    def test_returns_unchanged_string_when_no_nbsp(self):
        assert replace_nbsp("hello world") == "hello world"

    def test_returns_none_unchanged(self):
        assert replace_nbsp(None) is None

    def test_returns_empty_string_unchanged(self):
        assert replace_nbsp("") == ""


class TestSmartLinebreaks:
    """Tests for the smart_linebreaks filter."""

    def test_returns_empty_string_for_none(self):
        assert smart_linebreaks(None) == ""

    def test_returns_empty_string_for_empty_input(self):
        assert smart_linebreaks("") == ""

    def test_converts_single_linebreak_to_br(self):
        result = smart_linebreaks("line one\nline two")
        assert "<br>" in result

    def test_converts_double_linebreak_to_paragraph_break(self):
        result = smart_linebreaks("para one\n\npara two")
        assert "<br><br>" in result

    def test_collapses_excessive_linebreaks(self):
        # 3+ newlines should become at most 2
        result = smart_linebreaks("a\n\n\n\nb")
        # Should have double br separator but not more
        assert result.count("<br>") <= 3  # at most <br><br> separator + 0 inline

    def test_escapes_html_in_content(self):
        result = smart_linebreaks("<script>evil</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_result_is_mark_safe(self):
        from django.utils.safestring import SafeData

        result = smart_linebreaks("hello\nworld")
        assert isinstance(result, SafeData)
