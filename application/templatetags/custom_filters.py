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
import calendar
from datetime import datetime
import re
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_by_key(obj, key):
    """
    Get value from object by key.
    Works with dictionaries and objects with attributes.
    """
    if isinstance(obj, dict):
        return obj.get(key, 0)
    else:
        return getattr(obj, key, 0)


@register.filter
def list_index(value, arg):
    """
    Get item from list by index.
    """
    try:
        return value[int(arg)]
    except (IndexError, ValueError, TypeError):
        return ""


@register.filter
def month_last_day(month_key):
    """
    Convert YYYY-MM format to YYYY-MM-DD format with last day of month.
    Example: '2024-12' -> '2024-12-31'
    """
    try:
        year, month = month_key.split("-")
        year, month = int(year), int(month)
        last_day = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-{last_day:02d}"
    except (ValueError, AttributeError):
        return month_key


@register.filter
def replace_nbsp(value):
    """
    Replace non-breaking spaces (&nbsp;) with regular spaces.
    Useful for cleaning HTML content in text processing.
    """
    if value:
        return value.replace("\u00a0", " ").replace("&nbsp;", " ")
    return value


@register.filter
def smart_linebreaks(value):
    """
    Convert line breaks to HTML more intelligently than the default linebreaks filter.
    Prevents excessive spacing from email content by being more conservative with paragraph breaks.
    """
    if not value:
        return ""

    # Normalize line endings
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive consecutive line breaks (3+ becomes 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove trailing spaces from lines
    text = "\n".join(line.rstrip(" \t") for line in text.split("\n"))

    # Escape HTML
    from django.utils.html import escape

    text = escape(text)

    # Split into paragraphs on double line breaks
    paragraphs = text.split("\n\n")
    formatted_paragraphs = []

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if paragraph:
            # Convert single line breaks within paragraphs to <br>
            formatted_paragraph = paragraph.replace("\n", "<br>")
            formatted_paragraphs.append(formatted_paragraph)

    # Join paragraphs with a single <br><br> instead of <p> tags to reduce spacing
    return mark_safe("<br><br>".join(formatted_paragraphs))
