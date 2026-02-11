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
Template tags and filters for file handling utilities.
"""

import os
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

MISSING_FILE_IMAGE = "img/missing-file.svg"


@register.filter
def file_exists(file_path):
    """
    Check if a file exists in the media directory.

    Args:
        file_path: Relative path from MEDIA_ROOT

    Returns:
        Boolean indicating if file exists

    Usage:
        {% if attachment.file_path|file_exists %}
            <img src="{{ attachment.file_url }}" alt="{{ attachment.filename }}">
        {% else %}
            <div class="missing-file-placeholder">File not available</div>
        {% endif %}
    """
    if not file_path:
        return False

    try:
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        return os.path.exists(full_path)
    except (TypeError, ValueError):
        return False


@register.filter
def safe_image_url(attachment):
    """
    Get a safe image URL that falls back to a placeholder if the file doesn't exist.

    Args:
        attachment: EnquiryAttachment object

    Returns:
        URL to the image or a placeholder

    Usage:
        <img src="{{ attachment|safe_image_url }}" alt="{{ attachment.filename }}">
    """
    if not attachment or not hasattr(attachment, "file_path"):
        return static(MISSING_FILE_IMAGE)

    try:
        # Check if the file exists
        if attachment.file_path:
            full_path = os.path.join(settings.MEDIA_ROOT, attachment.file_path)
            if os.path.exists(full_path):
                return attachment.file_url

        # File doesn't exist, return placeholder based on file type
        filename = getattr(attachment, "filename", "").lower()

        if filename.endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif")
        ):
            return static("img/missing-image.svg")
        elif filename.endswith(".pdf"):
            return static("img/missing-pdf.svg")
        elif filename.endswith((".doc", ".docx")):
            return static("img/missing-doc.svg")
        else:
            return static(MISSING_FILE_IMAGE)

    except (TypeError, ValueError, AttributeError):
        return static(MISSING_FILE_IMAGE)


@register.inclusion_tag("partials/attachment_display.html")
def display_attachment(attachment):
    """
    Display an attachment with proper error handling for missing files.

    Args:
        attachment: EnquiryAttachment object

    Returns:
        Context for the attachment display template
    """
    context = {
        "attachment": attachment,
        "file_exists": False,
        "is_image": False,
        "is_pdf": False,
        "is_doc": False,
        "display_url": static(MISSING_FILE_IMAGE),
        "missing_file": True,
    }

    if not attachment:
        return context

    try:
        # Check if file exists
        if attachment.file_path:
            full_path = os.path.join(settings.MEDIA_ROOT, attachment.file_path)
            file_exists = os.path.exists(full_path)
            context["file_exists"] = file_exists
            context["missing_file"] = not file_exists

        # Determine file type
        filename = attachment.filename.lower() if attachment.filename else ""

        if filename.endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif")
        ):
            context["is_image"] = True
            if context["file_exists"]:
                context["display_url"] = attachment.file_url
            else:
                context["display_url"] = static("img/missing-image.svg")

        elif filename.endswith(".pdf"):
            context["is_pdf"] = True
            context["display_url"] = static("img/pdf-icon.svg")

        elif filename.endswith((".doc", ".docx")):
            context["is_doc"] = True
            context["display_url"] = static("img/word-icon.svg")

    except (TypeError, ValueError, AttributeError):
        pass

    return context


@register.simple_tag
def attachment_status_class(attachment):
    """
    Get CSS class for attachment status.

    Args:
        attachment: EnquiryAttachment object

    Returns:
        CSS class string
    """
    if not attachment or not hasattr(attachment, "file_path"):
        return "attachment-missing"

    try:
        if attachment.file_path:
            full_path = os.path.join(settings.MEDIA_ROOT, attachment.file_path)
            if os.path.exists(full_path):
                return "attachment-available"
        return "attachment-missing"
    except (TypeError, ValueError):
        return "attachment-missing"


@register.simple_tag
def attachment_status_text(attachment):
    """
    Get status text for attachment.

    Args:
        attachment: EnquiryAttachment object

    Returns:
        Status text string
    """
    if not attachment or not hasattr(attachment, "file_path"):
        return "File not available"

    try:
        if attachment.file_path:
            full_path = os.path.join(settings.MEDIA_ROOT, attachment.file_path)
            if os.path.exists(full_path):
                return "Available"
        return "File not found"
    except (TypeError, ValueError):
        return "File not available"
