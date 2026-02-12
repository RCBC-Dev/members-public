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
Tests for application/templatetags/dict_extras.py template filters.
"""

import pytest
from application.templatetags.dict_extras import (
    get_item,
    index,
    sum_list,
    column_sum,
    grand_total_sum,
)


class TestGetItem:
    """Tests for the get_item filter."""

    def test_returns_value_for_existing_key(self):
        assert get_item({"a": 1, "b": 2}, "a") == 1

    def test_returns_empty_string_for_missing_key(self):
        assert get_item({"a": 1}, "z") == ""

    def test_returns_empty_string_for_empty_dict(self):
        assert get_item({}, "key") == ""

    def test_works_with_string_values(self):
        assert get_item({"name": "Alice"}, "name") == "Alice"

    def test_missing_key_does_not_raise(self):
        # Should never raise, just return ""
        result = get_item({"x": 99}, "missing")
        assert result == ""


class TestIndex:
    """Tests for the index filter."""

    def test_returns_item_at_valid_position(self):
        assert index(["a", "b", "c"], 1) == "b"

    def test_returns_first_item(self):
        assert index([10, 20, 30], 0) == 10

    def test_returns_empty_string_for_out_of_range(self):
        assert index([1, 2], 5) == ""

    def test_returns_empty_string_for_non_numeric_position(self):
        assert index([1, 2, 3], "abc") == ""

    def test_returns_empty_string_for_none_position(self):
        assert index([1, 2, 3], None) == ""

    def test_works_with_string_position(self):
        # "2" should be coerced to int 2
        assert index(["x", "y", "z"], "2") == "z"


class TestSumList:
    """Tests for the sum_list filter."""

    def test_sums_integers(self):
        assert sum_list([1, 2, 3]) == 6

    def test_sums_floats(self):
        assert sum_list([1.5, 2.5]) == 4.0

    def test_ignores_non_numeric_items(self):
        assert sum_list([1, "oops", 2, None]) == 3

    def test_returns_zero_for_empty_list(self):
        assert sum_list([]) == 0

    def test_returns_zero_for_non_list_input(self):
        # Passing a non-list should not raise and should return 0
        assert sum_list("not a list") == 0

    def test_returns_zero_for_all_non_numeric(self):
        assert sum_list(["a", "b", None]) == 0


class TestColumnSum:
    """Tests for the column_sum filter."""

    def test_sums_a_valid_column(self):
        data = {"row1": [10, 20, 30], "row2": [1, 2, 3]}
        assert column_sum(data, 0) == 11  # 10 + 1
        assert column_sum(data, 1) == 22  # 20 + 2

    def test_returns_zero_for_out_of_range_column(self):
        data = {"row1": [1, 2]}
        assert column_sum(data, 5) == 0

    def test_returns_zero_for_non_numeric_column_index(self):
        data = {"row1": [1, 2, 3]}
        assert column_sum(data, "abc") == 0

    def test_returns_zero_for_empty_dict(self):
        assert column_sum({}, 0) == 0

    def test_ignores_non_numeric_values_in_column(self):
        data = {"row1": [5, "skip", 3], "row2": [2, "also_skip", 1]}
        assert column_sum(data, 1) == 0  # both are strings

    def test_returns_zero_for_non_dict_input(self):
        assert column_sum("not a dict", 0) == 0


class TestGrandTotalSum:
    """Tests for the grand_total_sum filter."""

    def test_sums_all_numeric_values(self):
        data = {"a": [1, 2], "b": [3, 4]}
        assert grand_total_sum(data) == 10

    def test_ignores_non_numeric_values(self):
        data = {"a": [1, "skip", 2], "b": [None, 3]}
        assert grand_total_sum(data) == 6

    def test_returns_zero_for_empty_dict(self):
        assert grand_total_sum({}) == 0

    def test_returns_zero_for_non_dict_input(self):
        assert grand_total_sum("not a dict") == 0

    def test_works_with_floats(self):
        data = {"x": [1.5, 2.5], "y": [0.5]}
        assert grand_total_sum(data) == 4.5
