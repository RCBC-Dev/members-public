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
Business logic services for the Members Enquiries System.

This module contains service classes that handle complex business logic,
keeping views thin and focused on HTTP handling.
"""

import json
import logging
import re
from datetime import date, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils import timezone

from .models import (
    Enquiry,
    EnquiryAttachment,
    EnquiryHistory,
    Member,
    Admin,
    Ward,
    JobType,
    Section,
    Contact,
)
from .utils import get_text_diff, strip_html_tags
from .date_range_service import DateRangeService

logger = logging.getLogger(__name__)
User = get_user_model()


class EnquiryFilterService:
    """Service for handling enquiry filtering and list view logic."""

    # Lookup table for predefined date range labels
    _DATE_RANGE_LABELS = {
        "3months": " in the last 3 months",
        "6months": " in the last 6 months",
        "12months": " in the last 12 months",
        "all": " in All Time",
    }

    # Lookup table for status display names
    _STATUS_LABELS = {
        "open": "Open",
        "closed": "Closed",
    }

    # Model filter lookups: (form_field, model_class, format_string, name_accessor)
    _MODEL_FILTER_LOOKUPS = [
        ("admin", Admin, " created by {name}", lambda obj: obj.user.get_full_name()),
        ("member", Member, " for {name}", lambda obj: obj.full_name),
        ("ward", Ward, " in {name}", lambda obj: obj.name),
        ("job_type", JobType, " for Job Type {name}", lambda obj: obj.name),
        ("section", Section, " (Section: {name})", lambda obj: obj.name),
        ("contact", Contact, " assigned to {name}", lambda obj: obj.name),
    ]

    @staticmethod
    def get_optimized_queryset(search_param: str = None):
        """
        Get optimized queryset based on whether search is being used.

        Args:
            search_param: Search term if any

        Returns:
            Optimized Enquiry queryset
        """
        # Smart optimization: Only defer description if NOT searching
        # Rationale:
        # - No search: Defer description for faster loading of large lists
        # - With search: Include description for powerful search, result set will be smaller anyway
        if not search_param:
            enquiries = (
                Enquiry.objects.select_related(
                    "member", "admin__user", "section", "job_type", "contact__section"
                )
                .prefetch_related("contact__areas", "contact__job_types")
                .defer("description")
            )
        else:
            enquiries = Enquiry.objects.select_related(
                "member", "admin__user", "section", "job_type", "contact__section"
            ).prefetch_related("contact__areas", "contact__job_types")

        return enquiries.order_by("-created_at")

    @staticmethod
    def get_default_filter_redirect(request_path: str):
        """
        Get redirect response with default filter parameters.

        Args:
            request_path: Current request path

        Returns:
            HttpResponseRedirect with default parameters
        """
        return DateRangeService.get_default_filter_redirect(request_path)

    @staticmethod
    def clean_url_parameters(request_get_params):
        """
        Clean up URL parameters, removing empty values and handling custom dates.

        Args:
            request_get_params: Request GET parameters

        Returns:
            Tuple of (clean_params dict, needs_redirect boolean)
        """
        return DateRangeService.clean_url_parameters(request_get_params)

    @staticmethod
    def _dates_match_predefined_range(date_from_str: str, date_to_str: str) -> bool:
        """Check if the provided dates match any predefined range using centralized calculation."""
        return DateRangeService.dates_match_predefined_range(date_from_str, date_to_str)

    @staticmethod
    def _build_status_prefix(cleaned_data):
        """Build the status prefix for the title (e.g. 'Open' or 'Closed')."""
        status = cleaned_data.get("status")
        label = EnquiryFilterService._STATUS_LABELS.get(status, "")
        if label:
            return f"{label} Members Enquiries"
        return "Members Enquiries"

    @staticmethod
    def _build_date_range_suffix(cleaned_data):
        """Build the date range portion of the title."""
        date_range = cleaned_data.get("date_range")

        # Check predefined ranges first
        if date_range in EnquiryFilterService._DATE_RANGE_LABELS:
            return EnquiryFilterService._DATE_RANGE_LABELS[date_range]

        # Custom date range (only if not a predefined range)
        is_custom = date_range in ("", "custom") or not date_range
        if not is_custom:
            return ""

        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")

        if date_from and date_to:
            return f" between {date_from.strftime('%d/%m/%Y')} and {date_to.strftime('%d/%m/%Y')}"
        if date_from:
            return f" from {date_from.strftime('%d/%m/%Y')}"
        if date_to:
            return f" until {date_to.strftime('%d/%m/%Y')}"
        return ""

    @staticmethod
    def _build_model_filter_suffix(cleaned_data):
        """Build title suffixes from model-based filters (admin, member, ward, etc.)."""
        parts = []
        for (
            field_name,
            model_class,
            fmt,
            name_accessor,
        ) in EnquiryFilterService._MODEL_FILTER_LOOKUPS:
            filter_value = cleaned_data.get(field_name)
            if not filter_value:
                continue
            try:
                select_related = ("user",) if model_class is Admin else ()
                obj = model_class.objects.select_related(*select_related).get(
                    id=filter_value
                )
                parts.append(fmt.format(name=name_accessor(obj)))
            except model_class.DoesNotExist:
                pass
        return "".join(parts)

    @staticmethod
    def generate_dynamic_title(filter_form):
        """
        Generate a dynamic title based on active filters.

        Args:
            filter_form: Validated EnquiryFilterForm

        Returns:
            str: Dynamic title like "{Status} Members Enquiries that contain 'search' in the last 3 months created by {Admin} for {Member} in {Ward} for Job Type {Job type} in {Section} or {Contact}"
        """
        if not filter_form.is_valid():
            return "Members Enquiries"

        cleaned_data = filter_form.cleaned_data
        title = EnquiryFilterService._build_status_prefix(cleaned_data)

        # Search parameter
        search = cleaned_data.get("search")
        if search:
            title += f" that contain '{search}'"

        # Date range
        title += EnquiryFilterService._build_date_range_suffix(cleaned_data)

        # Model-based filters
        title += EnquiryFilterService._build_model_filter_suffix(cleaned_data)

        # Overdue filter
        if cleaned_data.get("overdue_only"):
            title += " (overdue only)"

        return title

    @staticmethod
    def apply_filters(enquiries, filter_form):
        """
        Apply all filters from the form to the enquiry queryset.

        Args:
            enquiries: Base enquiry queryset
            filter_form: Validated EnquiryFilterForm

        Returns:
            Filtered enquiry queryset
        """
        if not filter_form.is_valid():
            return enquiries

        # Handle date filtering - both quick select and custom dates
        enquiries = EnquiryFilterService._apply_date_filters(enquiries, filter_form)

        # Apply all other filters
        status = filter_form.cleaned_data.get("status")
        if status:
            if status == "open":
                # 'Open' filter includes both 'new' and 'open' statuses
                enquiries = enquiries.filter(status__in=["new", "open"])
            else:
                enquiries = enquiries.filter(status=status)

        if filter_form.cleaned_data.get("member"):
            enquiries = enquiries.filter(member=filter_form.cleaned_data["member"])

        if filter_form.cleaned_data.get("admin"):
            enquiries = enquiries.filter(admin=filter_form.cleaned_data["admin"])

        if filter_form.cleaned_data.get("section"):
            enquiries = enquiries.filter(section=filter_form.cleaned_data["section"])

        if filter_form.cleaned_data.get("job_type"):
            enquiries = enquiries.filter(job_type=filter_form.cleaned_data["job_type"])

        if filter_form.cleaned_data.get("contact"):
            enquiries = enquiries.filter(contact=filter_form.cleaned_data["contact"])

        if filter_form.cleaned_data.get("ward"):
            enquiries = enquiries.filter(member__ward=filter_form.cleaned_data["ward"])

        if filter_form.cleaned_data.get("overdue_only"):
            overdue_date = timezone.now() - timedelta(
                days=settings.ENQUIRY_OVERDUE_DAYS
            )
            enquiries = enquiries.filter(
                status__in=["new", "open"], created_at__lt=overdue_date
            )

        # Apply search filter (searches reference, title, and description)
        if filter_form.cleaned_data.get("search"):
            search_term = filter_form.cleaned_data["search"]
            # Note: We can still search description even though it's deferred
            # Django will only load it if the search matches description content
            enquiries = enquiries.filter(
                Q(reference__icontains=search_term)
                | Q(title__icontains=search_term)
                | Q(description__icontains=search_term)
            )

        return enquiries

    @staticmethod
    def _apply_date_filters(enquiries, filter_form):
        """Apply date filtering logic."""
        return DateRangeService.apply_date_filters(enquiries, filter_form)


class EnquiryService:
    """Service for handling enquiry-related business logic."""

    # Fields to track for change detection, with display names and comparison types.
    # 'fk' fields use _compare_foreign_key, 'description' uses _compare_description,
    # 'simple' uses direct != comparison.
    _TRACKED_FIELDS = [
        ("title", "Title", "simple"),
        ("description", "Description", "description"),
        ("member", "Member", "fk"),
        ("contact", "Contact", "fk"),
        ("section", "Section", "fk"),
        ("job_type", "Job Type", "fk"),
    ]

    @staticmethod
    def create_enquiry_with_attachments(
        form_data: Dict, user, extracted_images_json: str = None
    ):
        """
        Create a new enquiry with optional image attachments.

        Args:
            form_data: Cleaned form data from EnquiryForm
            user: User creating the enquiry
            extracted_images_json: JSON string of extracted images from email

        Returns:
            Created Enquiry instance
        """
        with transaction.atomic():
            # Create the enquiry
            enquiry = Enquiry(**form_data)

            # Generate reference if not provided
            if not enquiry.reference:
                enquiry.reference = Enquiry.generate_reference()

            # Set the creating user for auto-assignment in model save method
            enquiry._creating_user = user
            enquiry.save()

            # Process extracted image attachments if provided
            attachment_counts = {"email": 0, "manual": 0, "total": 0}
            if extracted_images_json:
                attachment_counts = EnquiryService._process_extracted_images(
                    extracted_images_json, enquiry, user
                )

            # Create combined initial history entry with attachments
            EnquiryService._create_combined_creation_history_entry(
                enquiry, user, attachment_counts
            )

            # Note: Popular choices cache clearing should be handled in the view

            return enquiry

    @staticmethod
    def _process_extracted_images(
        extracted_images_json: str, enquiry: Enquiry, user: User
    ) -> dict:
        """
        Process extracted attachments (images and documents) from email and create EnquiryAttachment records.

        Args:
            extracted_images_json: JSON string containing attachment data
            enquiry: Enquiry to attach files to
            user: User uploading the attachments

        Returns:
            Dictionary with counts: {'email': count, 'manual': count, 'total': count}
        """
        try:
            extracted_images = json.loads(extracted_images_json)
            email_count = 0
            manual_count = 0
            filenames = []

            for attachment_data in extracted_images:
                filename = attachment_data.get("original_filename", "unknown")

                # Create EnquiryAttachment record
                EnquiryAttachment.objects.create(
                    enquiry=enquiry,
                    filename=filename,
                    file_path=attachment_data.get("file_path", ""),
                    file_size=attachment_data.get("file_size", 0),
                    uploaded_by=user,
                )

                # Count by upload type and collect filenames
                upload_type = attachment_data.get(
                    "upload_type", "extracted"
                )  # Default to 'extracted' for backward compatibility
                if upload_type == "manual":
                    manual_count += 1
                else:
                    email_count += 1

                filenames.append(filename)

            return {
                "email": email_count,
                "manual": manual_count,
                "total": email_count + manual_count,
                "filenames": filenames,
            }

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing extracted images: {e}")
            return {"email": 0, "manual": 0, "total": 0, "filenames": []}

    @staticmethod
    def _create_combined_creation_history_entry(
        enquiry: Enquiry, user: User, attachment_counts: dict
    ):
        """
        Create a combined history entry for enquiry creation with attachments.

        Args:
            enquiry: Enquiry that was created
            user: User who created the enquiry
            attachment_counts: Dictionary with email/manual/total counts and filenames
        """
        email_count = attachment_counts["email"]
        manual_count = attachment_counts["manual"]
        total_count = attachment_counts["total"]
        filenames = attachment_counts.get("filenames", [])

        # Start with base creation message
        note = "Enquiry created"

        # Add attachment information if any
        if total_count > 0:
            if email_count > 0 and manual_count > 0:
                # Mixed: both email and manual attachments
                note += f" with {email_count} file(s) from email and {manual_count} manually attached"
            elif email_count > 0:
                # Only email attachments
                note += f" with {email_count} file(s) from email"
            else:
                # Only manual attachments
                note += f" with {manual_count} manually attached file(s)"

            # Add filenames if available
            if filenames:
                note += f": {', '.join(filenames)}"

        EnquiryHistory.objects.create(
            enquiry=enquiry, note=note, note_type="enquiry_created", created_by=user
        )

    @staticmethod
    def _create_attachment_history_messages(
        attachment_counts: dict, enquiry: Enquiry, user: User
    ):
        """
        Create appropriate history messages for image attachments.
        Used when adding attachments to existing enquiries.

        Args:
            attachment_counts: Dictionary with email/manual/total counts and filenames
            enquiry: Enquiry to add history to
            user: User who uploaded the images
        """
        email_count = attachment_counts["email"]
        manual_count = attachment_counts["manual"]
        total_count = attachment_counts["total"]
        filenames = attachment_counts.get("filenames", [])

        if total_count == 0:
            return

        # Create history message based on attachment types
        if email_count > 0 and manual_count > 0:
            # Mixed: both email and manual attachments
            note = f"{email_count} file(s) from email, {manual_count} manually attached"
        elif email_count > 0:
            # Only email attachments
            note = f"{email_count} file(s) from email"
        else:
            # Only manual attachments
            note = f"{manual_count} file(s) manually attached"

        # Add filenames if available
        if filenames:
            note += f": {', '.join(filenames)}"

        EnquiryHistory.objects.create(
            enquiry=enquiry, note=note, note_type="attachment_added", created_by=user
        )

    @staticmethod
    def update_enquiry_status(
        enquiry: Enquiry, new_status: str, user: User, note: str = None
    ) -> None:
        """
        Update enquiry status and create history entry.

        Args:
            enquiry: Enquiry to update
            new_status: New status value
            user: User making the change
            note: Optional note for the history entry
        """
        if enquiry.status != new_status:
            old_status = enquiry.status
            enquiry.status = new_status
            enquiry.save()

            # Create history entry with appropriate note type
            history_note = note or f"Status changed from {old_status} to {new_status}"
            note_type = "enquiry_closed" if new_status == "closed" else "general"
            EnquiryHistory.objects.create(
                enquiry=enquiry, note=history_note, note_type=note_type, created_by=user
            )

    @staticmethod
    def close_enquiry(enquiry: Enquiry, user: User, service_type: str = None) -> bool:
        """
        Close an enquiry by changing status to 'closed'.

        Args:
            enquiry: Enquiry to close
            user: User closing the enquiry
            service_type: Service type classification (required for closure)

        Returns:
            True if enquiry was closed, False if already closed

        Raises:
            ValueError: If service_type is not provided or invalid
        """
        if enquiry.status != "closed":
            # Validate service_type is provided
            if not service_type:
                raise ValueError("service_type is required when closing an enquiry")

            # Validate service_type is a valid choice
            valid_choices = [choice[0] for choice in Enquiry.SERVICE_TYPE_CHOICES]
            if service_type not in valid_choices:
                raise ValueError(f"Invalid service_type: {service_type}")

            # Set service_type on enquiry
            enquiry.service_type = service_type
            enquiry.save(update_fields=["service_type"])

            EnquiryService.update_enquiry_status(
                enquiry,
                "closed",
                user,
                f"Enquiry closed (Service Type: {enquiry.get_service_type_display()}) - status changed from {enquiry.status} to closed",
            )
            return True
        return False

    @staticmethod
    def add_attachments_to_enquiry(
        enquiry: Enquiry, user: User, extracted_images_json: str
    ) -> None:
        """
        Add new image attachments to an existing enquiry.

        Args:
            enquiry: Existing enquiry to add attachments to
            user: User adding the attachments
            extracted_images_json: JSON string of image data
        """
        with transaction.atomic():
            # Process extracted image attachments
            attachment_counts = EnquiryService._process_extracted_images(
                extracted_images_json, enquiry, user
            )

            # Create appropriate history messages
            if attachment_counts["total"] > 0:
                EnquiryService._create_attachment_history_messages(
                    attachment_counts, enquiry, user
                )

    @staticmethod
    def _has_field_changed(field_name, compare_type, old_value, new_value):
        """
        Check if a single field has changed, using the appropriate comparison method.

        Args:
            field_name: Name of the field
            compare_type: One of 'simple', 'description', or 'fk'
            old_value: Current value on the enquiry
            new_value: New value from form data

        Returns:
            True if the field value has changed
        """
        if compare_type == "description":
            return EnquiryService._compare_description(old_value, new_value)
        if compare_type == "fk":
            return EnquiryService._compare_foreign_key(old_value, new_value)
        # simple comparison
        return old_value != new_value

    @staticmethod
    def _format_field_value(field_name, value):
        """
        Format a field value for display in change tracking.

        Args:
            field_name: Name of the field
            value: The value to format

        Returns:
            Formatted string representation
        """
        if not value:
            return "None"
        if field_name == "description":
            return strip_html_tags(str(value))
        return str(value)

    @staticmethod
    def _build_change_dict(field_name, display_name, old_value, new_value):
        """
        Build a change dictionary for a single field change.

        Args:
            field_name: Name of the field
            display_name: Human-readable field name
            old_value: Original value
            new_value: New value

        Returns:
            Dictionary with change information
        """
        old_formatted = EnquiryService._format_field_value(field_name, old_value)
        new_formatted = EnquiryService._format_field_value(field_name, new_value)

        change_dict = {
            "field_name": field_name,
            "display_name": display_name,
            "old_value": old_formatted,
            "new_value": new_formatted,
        }

        # For description field, also store raw values for diff
        if field_name == "description":
            change_dict["old_value_raw"] = old_value or ""
            change_dict["new_value_raw"] = new_value or ""

        return change_dict

    @staticmethod
    def track_enquiry_changes(enquiry: Enquiry, new_data: dict) -> list:
        """
        Track changes between current enquiry state and new form data.

        Args:
            enquiry: Current enquiry instance
            new_data: New form data (cleaned_data from form)

        Returns:
            List of dictionaries containing change information
        """
        changes = []

        for field_name, display_name, compare_type in EnquiryService._TRACKED_FIELDS:
            if field_name not in new_data:
                continue

            old_value = getattr(enquiry, field_name, None)
            new_value = new_data.get(field_name, None)

            if not EnquiryService._has_field_changed(
                field_name, compare_type, old_value, new_value
            ):
                continue

            changes.append(
                EnquiryService._build_change_dict(
                    field_name, display_name, old_value, new_value
                )
            )

        return changes

    @staticmethod
    def _compare_description(old_description, new_description):
        """
        Compare description fields, handling HTML content intelligently.
        """
        # Don't track empty description changes (TinyMCE can add/remove empty tags)
        if not old_description and not new_description:
            return False

        if isinstance(old_description, str) and isinstance(new_description, str):
            # Strip HTML tags and whitespace for comparison
            old_clean = re.sub(r"<[^>]+>", "", old_description).strip()
            new_clean = re.sub(r"<[^>]+>", "", new_description).strip()
            return old_clean != new_clean

        return old_description != new_description

    @staticmethod
    def _compare_foreign_key(old_obj, new_obj):
        """
        Compare foreign key objects, handling both model instances and IDs.

        Args:
            old_obj: Current model instance (or None)
            new_obj: New value from form (could be model instance, ID, or None)
        """
        # Get the old ID
        old_id = old_obj.id if old_obj else None

        # Handle new value - it could be a model instance or an ID
        if hasattr(new_obj, "id"):
            # new_obj is a model instance
            new_id = new_obj.id
        elif isinstance(new_obj, (int, str)) and new_obj:
            # new_obj is an ID (string or int)
            new_id = int(new_obj) if str(new_obj).isdigit() else None
        else:
            # new_obj is None or empty
            new_id = None

        return old_id != new_id

    @staticmethod
    def create_field_change_history_entries(
        enquiry: Enquiry, changes: list, user: User
    ) -> None:
        """
        Create history entries for field changes.

        Args:
            enquiry: Enquiry that was changed
            changes: List of change dictionaries from track_enquiry_changes
            user: User who made the changes
        """

        # Create a single history entry with all changes
        def format_change(change):
            """Format a single change, using diff for description field."""
            if change["field_name"] == "description":
                # Use diff for description changes
                diff_result = get_text_diff(
                    change["old_value_raw"], change["new_value_raw"]
                )
                if diff_result:
                    return f"Description updated: {diff_result}"
                else:
                    return "Description updated (no significant changes detected)"
            else:
                # Use standard format for other fields
                return f"{change['display_name']}: '{change['old_value']}' -> '{change['new_value']}'"

        if len(changes) == 1:
            change = changes[0]
            if change["field_name"] == "description":
                note = format_change(change)
            else:
                note = f"{change['display_name']} changed from '{change['old_value']}' to '{change['new_value']}'"
        else:
            # Multiple changes - create a summary
            change_list = []
            for change in changes:
                change_list.append(format_change(change))
            note = "Multiple fields updated:\n" + "\n".join(change_list)

        EnquiryHistory.objects.create(
            enquiry=enquiry, note=note, note_type="enquiry_edited", created_by=user
        )


class EmailProcessingService:
    """Service for handling email-related functionality."""

    # Email header patterns that indicate start of previous emails in a conversation
    _HEADER_PATTERNS = [
        r"From:\s+\w+",  # From: Name (internal) or From: email@domain.com
        r"Sent:\s+.+",  # Sent: date/time
        r"To:\s+.+",  # To: recipient(s)
        r"Subject:\s+.+",  # Subject: text
        r"On\s+.+wrote:",  # On [date] [person] wrote:
        r"On\s+.+said:",  # On [date] [person] said:
        r"_{10,}",  # Long underscores (Outlook separator)
        r"-{5,}Original Message-{5,}",  # -----Original Message-----
        r"-{3,}\s*Original Message\s*-{3,}",  # --- Original Message ---
    ]

    # Fallback separators for short extraction results
    _FALLBACK_SEPARATORS = ["From:", "Sent:", "-----Original", "--- Original"]

    @staticmethod
    def _convert_html_to_plain_text(email_body):
        """
        Convert HTML email body to plain text, handling br tags appropriately.

        Args:
            email_body: Raw email body string (may contain HTML)

        Returns:
            Plain text version of the email body
        """
        if "<" not in email_body or ">" not in email_body:
            return email_body

        from bs4 import BeautifulSoup

        # Replace multiple <br> tags with double newlines (paragraph breaks)
        email_body = re.sub(
            r"(<br\s*/?>\s*){2,}", "\n\n", email_body, flags=re.IGNORECASE
        )

        # Replace single <br> tags with single newlines
        email_body = re.sub(r"<br\s*/?>", "\n", email_body, flags=re.IGNORECASE)

        soup = BeautifulSoup(email_body, "html.parser")
        return soup.get_text()

    @staticmethod
    def _line_is_separator(line_stripped):
        """
        Check if a line matches any email header/separator pattern.

        Args:
            line_stripped: Stripped line text to check

        Returns:
            Matched pattern string if found, None otherwise
        """
        for pattern in EmailProcessingService._HEADER_PATTERNS:
            if re.search(pattern, line_stripped, re.IGNORECASE):
                return pattern
        return None

    @staticmethod
    def _extract_lines_before_separator(lines):
        """
        Extract lines from the email body up to the first separator or quoted text.

        Args:
            lines: List of lines from the email body

        Returns:
            List of lines belonging to the latest email
        """
        latest_email_lines = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines at the start
            if not latest_email_lines and not line_stripped:
                continue

            # DEBUG: Log line processing
            if i < 50:  # Only log first 50 lines to avoid spam
                logger.info(f"Processing line {i}: {repr(line_stripped[:100])}")

            # Check if this line matches any email header pattern
            matched_pattern = EmailProcessingService._line_is_separator(line_stripped)
            if matched_pattern:
                logger.info(
                    f"SEPARATOR FOUND! Line {i}: {repr(line_stripped)} matched pattern: {matched_pattern}"
                )
                break

            # Also check for quoted text (lines starting with >)
            if line_stripped.startswith(">"):
                logger.info(f"QUOTED TEXT FOUND! Line {i}: {repr(line_stripped)}")
                break

            latest_email_lines.append(line)

        return latest_email_lines

    @staticmethod
    def _clean_extracted_text(text):
        """
        Clean up extracted email text by removing excessive whitespace and HTML entities.

        Args:
            text: Raw extracted email text

        Returns:
            Cleaned text string
        """
        # Remove multiple consecutive newlines
        text = re.sub(r"\n[^\S\n]*\n[^\S\n]*\n+", "\n\n", text)

        # Remove leading/trailing whitespace from each line
        lines = text.split("\n")
        cleaned_lines = [line.rstrip() for line in lines]
        text = "\n".join(cleaned_lines)

        # Remove any remaining HTML entities
        text = re.sub(r"&[a-zA-Z0-9#]+;", "", text)

        return text.strip()

    @staticmethod
    def _try_fallback_extraction(email_body):
        """
        Try splitting by common separators as a fallback when primary extraction yields little text.

        Args:
            email_body: Full email body text

        Returns:
            Extracted text if a suitable split was found, None otherwise
        """
        for separator in EmailProcessingService._FALLBACK_SEPARATORS:
            if separator not in email_body:
                continue
            parts = email_body.split(separator, 1)
            if len(parts[0].strip()) > 50:
                return parts[0].strip()
        return None

    @staticmethod
    def extract_latest_email_from_conversation(email_body: str) -> str:
        """
        Extract the latest email from a conversation thread.
        Looks for common email separators and returns only the most recent message.
        """
        logger.info("=== EXTRACT LATEST EMAIL DEBUG ===")
        logger.info(f"Input email_body length: {len(email_body) if email_body else 0}")
        logger.info(
            f"Input email_body preview: {repr(email_body[:200]) if email_body else 'None'}"
        )
        if not email_body:
            return ""

        # Convert HTML to plain text
        email_body = EmailProcessingService._convert_html_to_plain_text(email_body)

        # Split into lines and extract up to first separator
        lines = email_body.split("\n")
        latest_email_lines = EmailProcessingService._extract_lines_before_separator(
            lines
        )

        # Join and clean up the extracted text
        latest_email = "\n".join(latest_email_lines).strip()
        latest_email = EmailProcessingService._clean_extracted_text(latest_email)

        # If we didn't extract much, try a different approach
        if len(latest_email) < 50 and len(email_body) > 100:
            fallback = EmailProcessingService._try_fallback_extraction(email_body)
            if fallback:
                latest_email = fallback

        # DEBUG: Log final result
        result = latest_email if latest_email and len(latest_email) > 10 else email_body
        logger.info(f"Extract latest result length: {len(result)}")
        logger.info(f"Extract latest result preview: {repr(result[:200])}")
        logger.info("=== EXTRACT LATEST EMAIL DEBUG END ===")

        return result

    @staticmethod
    def clean_html_for_display(html_content: str) -> str:
        """
        Clean HTML content for better plain text display.
        Removes excessive <br> tags and converts to readable plain text.
        """
        if not html_content:
            return ""

        from bs4 import BeautifulSoup

        # Replace multiple <br> tags with double newlines
        html_content = re.sub(
            r"(<br\s*/?>\s*){2,}", "\n\n", html_content, flags=re.IGNORECASE
        )

        # Replace single <br> tags with single newlines
        html_content = re.sub(r"<br\s*/?>", "\n", html_content, flags=re.IGNORECASE)

        # Convert to plain text
        soup = BeautifulSoup(html_content, "html.parser")
        plain_text = soup.get_text()

        # Clean up excessive whitespace
        plain_text = re.sub(r"\n[^\S\n]*\n[^\S\n]*\n+", "\n\n", plain_text)
        plain_text = re.sub(
            r"[ \t]+", " ", plain_text
        )  # Multiple spaces to single space

        # Remove leading/trailing whitespace from each line
        lines = plain_text.split("\n")
        cleaned_lines = [line.strip() for line in lines]

        # Remove empty lines at start and end, but preserve internal structure
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()

        return "\n".join(cleaned_lines)

    @staticmethod
    def process_email_for_history(email_data: Dict) -> Dict:
        """
        Process email data for adding to enquiry history.

        Args:
            email_data: Dictionary containing email information

        Returns:
            Processed email data ready for history entry
        """
        logger.info("=== PROCESS EMAIL FOR HISTORY DEBUG ===")
        logger.info(
            f"Input email_data keys: {list(email_data.keys()) if email_data else 'None'}"
        )
        if email_data:
            body_content = email_data.get("body_content", "")
            logger.info(f"body_content length: {len(body_content)}")
            logger.info(f"body_content preview: {repr(body_content[:200])}")
        if not email_data:
            return {}

        # Extract the latest email from the conversation
        latest_email = EmailProcessingService.extract_latest_email_from_conversation(
            email_data.get("body_content", "")
        )

        # Clean up the full conversation for display
        full_conversation = EmailProcessingService.clean_html_for_display(
            email_data.get("body_content", "")
        )

        result = {
            "subject": email_data.get("subject", ""),
            "from": email_data.get("email_from", ""),
            "to": email_data.get("email_to", ""),
            "cc": email_data.get("email_cc", ""),
            "date": email_data.get("email_date_str", ""),
            "body": latest_email,
            "direction": email_data.get("direction", "UNKNOWN"),
            "full_conversation": full_conversation,
        }

        return result


class MemberService:
    """Service for handling member-related functionality."""

    @staticmethod
    def find_member_by_email(email: str) -> Optional[Member]:
        """
        Find an active member by email address.

        Delegates to unified email service for consistency.

        Args:
            email: Email address to search for

        Returns:
            Member instance if found, None otherwise
        """
        from .email_service import EmailProcessingService as UnifiedEmailService

        return UnifiedEmailService.find_member_by_email(email)

    @staticmethod
    def get_member_info(member: Member) -> Dict:
        """
        Get formatted member information.

        Args:
            member: Member instance

        Returns:
            Dictionary with member information
        """
        if not member:
            return {}

        return {
            "id": member.id,
            "name": member.full_name,
            "email": member.email,
            "ward": member.ward.name if member.ward else "Unknown",
        }
