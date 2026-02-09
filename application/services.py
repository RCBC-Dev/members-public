"""
Business logic services for the Members Enquiries System.

This module contains service classes that handle complex business logic,
keeping views thin and focused on HTTP handling.
"""

import json
import logging
from datetime import date, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils import timezone

from .models import Enquiry, EnquiryAttachment, EnquiryHistory, Member, Admin, Ward, JobType, Section, Contact
from .utils import get_text_diff, strip_html_tags
from .date_range_service import DateRangeService

logger = logging.getLogger(__name__)
User = get_user_model()


class EnquiryFilterService:
    """Service for handling enquiry filtering and list view logic."""

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
            enquiries = Enquiry.objects.select_related(
                'member', 'admin__user', 'section', 'job_type', 'contact__section'
            ).prefetch_related(
                'contact__areas', 'contact__job_types'
            ).defer('description')
        else:
            enquiries = Enquiry.objects.select_related(
                'member', 'admin__user', 'section', 'job_type', 'contact__section'
            ).prefetch_related(
                'contact__areas', 'contact__job_types'
            )

        return enquiries.order_by('-created_at')

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
        
        title_parts = []
        base_title = "Members Enquiries"
        
        # Status filter
        status = filter_form.cleaned_data.get('status')
        if status:
            if status == 'open':
                title_parts.append("Open")
            elif status == 'closed':
                title_parts.append("Closed")
        
        # Start building the title
        if title_parts:
            title = f"{' '.join(title_parts)} {base_title}"
        else:
            title = base_title
        
        # Search parameter
        search = filter_form.cleaned_data.get('search')
        if search:
            title += f" that contain '{search}'"
        
        # Date range handling
        date_range = filter_form.cleaned_data.get('date_range')
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        
        if date_range and date_range in ['3months', '6months', '12months', 'all']:
            # Predefined date range - always prioritize this over custom dates
            if date_range == '3months':
                title += " in the last 3 months"
            elif date_range == '6months':
                title += " in the last 6 months"
            elif date_range == '12months':
                title += " in the last 12 months"
            elif date_range == 'all':
                title += " in All Time"
        elif (date_range in ['', 'custom'] or not date_range) and (date_from or date_to):
            # Custom date range (only use if not using predefined range)
            if date_from and date_to:
                title += f" between {date_from.strftime('%d/%m/%Y')} and {date_to.strftime('%d/%m/%Y')}"
            elif date_from:
                title += f" from {date_from.strftime('%d/%m/%Y')}"
            elif date_to:
                title += f" until {date_to.strftime('%d/%m/%Y')}"
        
        # Admin filter
        admin = filter_form.cleaned_data.get('admin')
        if admin:
            try:
                admin_obj = Admin.objects.select_related('user').get(id=admin)
                admin_name = admin_obj.user.get_full_name()
                title += f" created by {admin_name}"
            except Admin.DoesNotExist:
                pass
        
        # Member filter
        member = filter_form.cleaned_data.get('member')
        if member:
            try:
                member_obj = Member.objects.get(id=member)
                member_name = member_obj.full_name
                title += f" for {member_name}"
            except Member.DoesNotExist:
                pass
        
        # Ward filter
        ward = filter_form.cleaned_data.get('ward')
        if ward:
            try:
                ward_obj = Ward.objects.get(id=ward)
                title += f" in {ward_obj.name}"
            except Ward.DoesNotExist:
                pass
        
        # Job Type filter
        job_type = filter_form.cleaned_data.get('job_type')
        if job_type:
            try:
                job_type_obj = JobType.objects.get(id=job_type)
                title += f" for Job Type {job_type_obj.name}"
            except JobType.DoesNotExist:
                pass
        
        # Section filter
        section = filter_form.cleaned_data.get('section')
        if section:
            try:
                section_obj = Section.objects.get(id=section)
                title += f" (Section: {section_obj.name})"
            except Section.DoesNotExist:
                pass
        
        # Contact filter
        contact = filter_form.cleaned_data.get('contact')
        if contact:
            try:
                contact_obj = Contact.objects.get(id=contact)
                title += f" assigned to {contact_obj.name}"
            except Contact.DoesNotExist:
                pass
        
        # Overdue filter
        overdue_only = filter_form.cleaned_data.get('overdue_only')
        if overdue_only:
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
        status = filter_form.cleaned_data.get('status')
        if status:
            if status == 'open':
                # 'Open' filter includes both 'new' and 'open' statuses
                enquiries = enquiries.filter(status__in=['new', 'open'])
            else:
                enquiries = enquiries.filter(status=status)

        if filter_form.cleaned_data.get('member'):
            enquiries = enquiries.filter(member=filter_form.cleaned_data['member'])

        if filter_form.cleaned_data.get('admin'):
            enquiries = enquiries.filter(admin=filter_form.cleaned_data['admin'])

        if filter_form.cleaned_data.get('section'):
            enquiries = enquiries.filter(section=filter_form.cleaned_data['section'])

        if filter_form.cleaned_data.get('job_type'):
            enquiries = enquiries.filter(job_type=filter_form.cleaned_data['job_type'])

        if filter_form.cleaned_data.get('contact'):
            enquiries = enquiries.filter(contact=filter_form.cleaned_data['contact'])

        if filter_form.cleaned_data.get('ward'):
            enquiries = enquiries.filter(member__ward=filter_form.cleaned_data['ward'])

        if filter_form.cleaned_data.get('overdue_only'):
            overdue_date = timezone.now() - timedelta(days=settings.ENQUIRY_OVERDUE_DAYS)
            enquiries = enquiries.filter(
                status__in=['new', 'open'],
                created_at__lt=overdue_date
            )

        # Apply search filter (searches reference, title, and description)
        if filter_form.cleaned_data.get('search'):
            search_term = filter_form.cleaned_data['search']
            # Note: We can still search description even though it's deferred
            # Django will only load it if the search matches description content
            enquiries = enquiries.filter(
                Q(reference__icontains=search_term) |
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        return enquiries

    @staticmethod
    def _apply_date_filters(enquiries, filter_form):
        """Apply date filtering logic."""
        return DateRangeService.apply_date_filters(enquiries, filter_form)


class EnquiryService:
    """Service for handling enquiry-related business logic."""
    
    @staticmethod
    def create_enquiry_with_attachments(form_data: Dict, user, extracted_images_json: str = None):
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
            attachment_counts = {'email': 0, 'manual': 0, 'total': 0}
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
    def _process_extracted_images(extracted_images_json: str, enquiry: Enquiry, user: User) -> dict:
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
                filename = attachment_data.get('original_filename', 'unknown')

                # Create EnquiryAttachment record
                EnquiryAttachment.objects.create(
                    enquiry=enquiry,
                    filename=filename,
                    file_path=attachment_data.get('file_path', ''),
                    file_size=attachment_data.get('file_size', 0),
                    uploaded_by=user
                )

                # Count by upload type and collect filenames
                upload_type = attachment_data.get('upload_type', 'extracted')  # Default to 'extracted' for backward compatibility
                if upload_type == 'manual':
                    manual_count += 1
                else:
                    email_count += 1

                filenames.append(filename)

            return {
                'email': email_count,
                'manual': manual_count,
                'total': email_count + manual_count,
                'filenames': filenames
            }

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing extracted images: {e}")
            return {'email': 0, 'manual': 0, 'total': 0, 'filenames': []}

    @staticmethod
    def _create_combined_creation_history_entry(enquiry: Enquiry, user: User, attachment_counts: dict):
        """
        Create a combined history entry for enquiry creation with attachments.

        Args:
            enquiry: Enquiry that was created
            user: User who created the enquiry
            attachment_counts: Dictionary with email/manual/total counts and filenames
        """
        email_count = attachment_counts['email']
        manual_count = attachment_counts['manual']
        total_count = attachment_counts['total']
        filenames = attachment_counts.get('filenames', [])

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
            enquiry=enquiry,
            note=note,
            note_type='enquiry_created',
            created_by=user
        )

    @staticmethod
    def _create_attachment_history_messages(attachment_counts: dict, enquiry: Enquiry, user: User):
        """
        Create appropriate history messages for image attachments.
        Used when adding attachments to existing enquiries.

        Args:
            attachment_counts: Dictionary with email/manual/total counts and filenames
            enquiry: Enquiry to add history to
            user: User who uploaded the images
        """
        email_count = attachment_counts['email']
        manual_count = attachment_counts['manual']
        total_count = attachment_counts['total']
        filenames = attachment_counts.get('filenames', [])

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
            enquiry=enquiry,
            note=note,
            note_type='attachment_added',
            created_by=user
        )
    
    @staticmethod
    def update_enquiry_status(enquiry: Enquiry, new_status: str, user: User, note: str = None) -> None:
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
            history_note = note or f'Status changed from {old_status} to {new_status}'
            note_type = 'enquiry_closed' if new_status == 'closed' else 'general'
            EnquiryHistory.objects.create(
                enquiry=enquiry,
                note=history_note,
                note_type=note_type,
                created_by=user
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
        if enquiry.status != 'closed':
            # Validate service_type is provided
            if not service_type:
                raise ValueError("service_type is required when closing an enquiry")

            # Validate service_type is a valid choice
            valid_choices = [choice[0] for choice in Enquiry.SERVICE_TYPE_CHOICES]
            if service_type not in valid_choices:
                raise ValueError(f"Invalid service_type: {service_type}")

            # Set service_type on enquiry
            enquiry.service_type = service_type
            enquiry.save(update_fields=['service_type'])

            EnquiryService.update_enquiry_status(
                enquiry, 'closed', user,
                f'Enquiry closed (Service Type: {enquiry.get_service_type_display()}) - status changed from {enquiry.status} to closed'
            )
            return True
        return False
    
    @staticmethod
    def add_attachments_to_enquiry(enquiry: Enquiry, user: User, extracted_images_json: str) -> None:
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
            if attachment_counts['total'] > 0:
                EnquiryService._create_attachment_history_messages(
                    attachment_counts, enquiry, user
                )

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
        
        # Helper function to get status display name
        def format_status(status_value):
            if not status_value:
                return 'None'
            status_choices = dict(enquiry.STATUS_CHOICES)
            return status_choices.get(status_value, status_value.title())
        
        # Define fields to track with their comparison and formatting functions
        # Only include fields that are actually in the form data
        fields_to_track = {
            'title': {
                'display_name': 'Title',
                'compare_func': lambda old, new: old != new,
                'format_func': lambda x: str(x) if x else 'None'
            },
            'description': {
                'display_name': 'Description',
                'compare_func': EnquiryService._compare_description,
                'format_func': lambda x: strip_html_tags(str(x)) if x else 'None'
            },
            'member': {
                'display_name': 'Member',
                'compare_func': lambda old, new: EnquiryService._compare_foreign_key(old, new),
                'format_func': lambda x: str(x) if x else 'None'
            },
            'contact': {
                'display_name': 'Contact',
                'compare_func': lambda old, new: EnquiryService._compare_foreign_key(old, new),
                'format_func': lambda x: str(x) if x else 'None'
            },
            'section': {
                'display_name': 'Section',
                'compare_func': lambda old, new: EnquiryService._compare_foreign_key(old, new),
                'format_func': lambda x: str(x) if x else 'None'
            },
            'job_type': {
                'display_name': 'Job Type',
                'compare_func': lambda old, new: EnquiryService._compare_foreign_key(old, new),
                'format_func': lambda x: str(x) if x else 'None'
            },
        }
        
        # Only check fields that are present in the form data
        for field_name, field_info in fields_to_track.items():
            if field_name not in new_data:
                continue  # Skip fields not in the form
                
            old_value = getattr(enquiry, field_name, None)
            new_value = new_data.get(field_name, None)
            
            # Check if there's actually a change
            if field_info['compare_func'](old_value, new_value):
                old_formatted = field_info['format_func'](old_value)
                new_formatted = field_info['format_func'](new_value)
                
                change_dict = {
                    'field_name': field_name,
                    'display_name': field_info['display_name'],
                    'old_value': old_formatted,
                    'new_value': new_formatted,
                }
                
                # For description field, also store raw values for diff
                if field_name == 'description':
                    change_dict['old_value_raw'] = old_value or ""
                    change_dict['new_value_raw'] = new_value or ""
                
                changes.append(change_dict)
        
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
            import re
            old_clean = re.sub(r'<[^>]+>', '', old_description).strip()
            new_clean = re.sub(r'<[^>]+>', '', new_description).strip()
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
        if hasattr(new_obj, 'id'):
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
    def create_field_change_history_entries(enquiry: Enquiry, changes: list, user: User) -> None:
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
            if change['field_name'] == 'description':
                # Use diff for description changes
                diff_result = get_text_diff(change['old_value_raw'], change['new_value_raw'])
                if diff_result:
                    return f"Description updated: {diff_result}"
                else:
                    return "Description updated (no significant changes detected)"
            else:
                # Use standard format for other fields
                return f"{change['display_name']}: '{change['old_value']}' → '{change['new_value']}'"
        
        if len(changes) == 1:
            change = changes[0]
            if change['field_name'] == 'description':
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
            enquiry=enquiry,
            note=note,
            note_type='enquiry_edited',
            created_by=user
        )


class EmailProcessingService:
    """Service for handling email-related functionality."""
    
    @staticmethod
    def extract_latest_email_from_conversation(email_body: str) -> str:
        """
        Extract the latest email from a conversation thread.
        Looks for common email separators and returns only the most recent message.
        """
        logger.info(f"=== EXTRACT LATEST EMAIL DEBUG ===")
        logger.info(f"Input email_body length: {len(email_body) if email_body else 0}")
        logger.info(f"Input email_body preview: {repr(email_body[:200]) if email_body else 'None'}")
        if not email_body:
            return ""
        
        # Convert HTML to plain text and clean up formatting
        if '<' in email_body and '>' in email_body:
            from bs4 import BeautifulSoup
            import re

            # Use the same smart HTML processing as clean_html_for_display
            # Replace multiple <br> tags with double newlines (paragraph breaks)
            email_body = re.sub(r'(<br\s*/?>\s*){2,}', '\n\n', email_body, flags=re.IGNORECASE)

            # Replace single <br> tags with single newlines
            email_body = re.sub(r'<br\s*/?>', '\n', email_body, flags=re.IGNORECASE)

            soup = BeautifulSoup(email_body, 'html.parser')
            email_body = soup.get_text()
        
        # More comprehensive email separators with exact patterns
        import re
        
        # Look for email header patterns that indicate start of previous emails
        header_patterns = [
            r'From:\s+\w+',    # From: Name (internal) or From: email@domain.com
            r'Sent:\s+.+',     # Sent: date/time
            r'To:\s+.+',       # To: recipient(s)
            r'Subject:\s+.+',  # Subject: text
            r'On\s+.+wrote:',  # On [date] [person] wrote:
            r'On\s+.+said:',   # On [date] [person] said:
            r'_{10,}',         # Long underscores (Outlook separator)
            r'-{5,}Original Message-{5,}',  # -----Original Message-----
            r'-{3,}\s*Original Message\s*-{3,}',  # --- Original Message ---
        ]
        
        # Split into lines and process
        lines = email_body.split('\n')
        latest_email_lines = []
        found_separator = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines at the start
            if not latest_email_lines and not line_stripped:
                continue

            # DEBUG: Log line processing
            if i < 50:  # Only log first 50 lines to avoid spam
                logger.info(f"Processing line {i}: {repr(line_stripped[:100])}")

            # Check if this line matches any email header pattern
            for pattern in header_patterns:
                if re.search(pattern, line_stripped, re.IGNORECASE):
                    logger.info(f"SEPARATOR FOUND! Line {i}: {repr(line_stripped)} matched pattern: {pattern}")
                    found_separator = True
                    break

            if found_separator:
                break

            # Also check for quoted text (lines starting with >)
            if line_stripped.startswith('>'):
                logger.info(f"QUOTED TEXT FOUND! Line {i}: {repr(line_stripped)}")
                break

            latest_email_lines.append(line)
        
        # Join the lines and clean up
        latest_email = '\n'.join(latest_email_lines).strip()
        
        # Clean up excessive whitespace and formatting
        import re
        
        # Remove multiple consecutive newlines
        latest_email = re.sub(r'\n\s*\n\s*\n+', '\n\n', latest_email)
        
        # Remove leading/trailing whitespace from each line
        lines = latest_email.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        latest_email = '\n'.join(cleaned_lines)
        
        # Remove any remaining HTML entities
        latest_email = re.sub(r'&[a-zA-Z0-9#]+;', '', latest_email)
        
        # Final cleanup
        latest_email = latest_email.strip()
        
        # If we didn't extract much, try a different approach
        if len(latest_email) < 50 and len(email_body) > 100:
            # Try splitting by common separators as fallback
            for separator in ['From:', 'Sent:', '-----Original', '--- Original']:
                if separator in email_body:
                    parts = email_body.split(separator, 1)
                    if len(parts[0].strip()) > 50:
                        latest_email = parts[0].strip()
                        break
        
        # DEBUG: Log final result
        result = latest_email if latest_email and len(latest_email) > 10 else email_body
        logger.info(f"Extract latest result length: {len(result)}")
        logger.info(f"Extract latest result preview: {repr(result[:200])}")
        logger.info(f"=== EXTRACT LATEST EMAIL DEBUG END ===")

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
        import re
        
        # Replace multiple <br> tags with double newlines
        html_content = re.sub(r'(<br\s*/?>\s*){2,}', '\n\n', html_content, flags=re.IGNORECASE)
        
        # Replace single <br> tags with single newlines
        html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        
        # Convert to plain text
        soup = BeautifulSoup(html_content, 'html.parser')
        plain_text = soup.get_text()
        
        # Clean up excessive whitespace
        plain_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', plain_text)
        plain_text = re.sub(r'[ \t]+', ' ', plain_text)  # Multiple spaces to single space
        
        # Remove leading/trailing whitespace from each line
        lines = plain_text.split('\n')
        cleaned_lines = [line.strip() for line in lines]
        
        # Remove empty lines at start and end, but preserve internal structure
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)
    
    @staticmethod
    def process_email_for_history(email_data: Dict) -> Dict:
        """
        Process email data for adding to enquiry history.

        Args:
            email_data: Dictionary containing email information

        Returns:
            Processed email data ready for history entry
        """
        logger.info(f"=== PROCESS EMAIL FOR HISTORY DEBUG ===")
        logger.info(f"Input email_data keys: {list(email_data.keys()) if email_data else 'None'}")
        if email_data:
            body_content = email_data.get('body_content', '')
            logger.info(f"body_content length: {len(body_content)}")
            logger.info(f"body_content preview: {repr(body_content[:200])}")
        if not email_data:
            return {}
        
        # Extract the latest email from the conversation
        latest_email = EmailProcessingService.extract_latest_email_from_conversation(
            email_data.get('body_content', '')
        )
        
        # Clean up the full conversation for display
        full_conversation = EmailProcessingService.clean_html_for_display(
            email_data.get('body_content', '')
        )
        
        result = {
            'subject': email_data.get('subject', ''),
            'from': email_data.get('email_from', ''),
            'to': email_data.get('email_to', ''),
            'cc': email_data.get('email_cc', ''),
            'date': email_data.get('email_date_str', ''),
            'body': latest_email,
            'direction': email_data.get('direction', 'UNKNOWN'),
            'full_conversation': full_conversation,
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
            'id': member.id,
            'name': member.full_name,
            'email': member.email,
            'ward': member.ward.name if member.ward else 'Unknown'
        }