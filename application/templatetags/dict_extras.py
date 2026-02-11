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

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, "")


@register.filter
def index(sequence, position):
    try:
        return sequence[int(position)]
    except (IndexError, ValueError, TypeError):
        return ""


@register.filter
def sum_list(value_list):
    """Sums the items in a list, ignoring non-numeric types gracefully."""
    total = 0
    if isinstance(value_list, list):
        for item in value_list:
            if isinstance(item, (int, float)):
                total += item
    return total


@register.filter
def column_sum(data_dict, column_index):
    """Sums the items in a specific column of a dictionary of lists."""
    total = 0
    try:
        idx = int(column_index)
        if isinstance(data_dict, dict):
            for key in data_dict:
                if isinstance(data_dict[key], list) and idx < len(data_dict[key]):
                    item = data_dict[key][idx]
                    if isinstance(item, (int, float)):
                        total += item
    except (ValueError, TypeError):
        pass  # Ignore if column_index is not a valid int or other type errors
    return total


@register.filter
def grand_total_sum(data_dict):
    """Sums all numeric items in all lists within a dictionary of lists."""
    grand_total = 0
    if isinstance(data_dict, dict):
        for key in data_dict:
            if isinstance(data_dict[key], list):
                for item in data_dict[key]:
                    if isinstance(item, (int, float)):
                        grand_total += item
    return grand_total
