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

# This file is for utility functions used across the application.
import html
import io
import logging
import mimetypes
import os
import re
import uuid
from datetime import datetime, timedelta
from email.utils import parseaddr
from functools import wraps

# Third-party imports
import extract_msg
import pytz

# Django imports
from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.timezone import make_aware

logger = logging.getLogger(__name__)

# Local imports - moved here to avoid inline imports  
try:
    from .models import Admin, Enquiry, EnquiryHistory, JobType, Member, Section
except ImportError:
    # Handle circular import by keeping these as inline imports
    Admin = Enquiry = EnquiryHistory = JobType = Member = Section = None


def _format_recipient_list(recipients_str: str) -> str:
    """
    Parses a semicolon-separated string of email recipients into a formatted string.
    Example input: "Name1 <email1@a.com>; email2@b.com"
    Example output: "Name1 <email1@a.com>; email2@b.com"
    """
    if not recipients_str:
        return ""
    
    recipient_list = []
    # Split entries by semicolon and process each one
    raw_entries = recipients_str.split(';')
    for entry in raw_entries:
        entry = entry.strip()
        if not entry:
            continue
        
        # Use email.utils.parseaddr to robustly split name and address
        name, addr = parseaddr(entry)
        if name and addr:
            recipient_list.append(f"{name} <{addr}>")
        elif addr:  # Only email address is valid
            recipient_list.append(addr)
        elif entry:  # Fallback to the original entry if parsing is incomplete
            recipient_list.append(entry)
            
    return "; ".join(recipient_list)


def _parse_sender_info(msg_obj):
    """Parses sender information from a message object."""
    raw_from = msg_obj.sender or ""
    sender_name = getattr(msg_obj, 'sender_name', '')
    sender_email = getattr(msg_obj, 'sender_email', '')

    if not sender_email and raw_from:
        _, sender_email = parseaddr(raw_from)

    # Construct the final 'from' string
    if sender_name and sender_email:
        email_from = f"{sender_name} <{sender_email}>"
    elif sender_email:
        email_from = sender_email
    else:
        email_from = raw_from or "Unknown Sender"
        
    return email_from, raw_from


def _parse_email_date(msg_obj):
    """Parses the date from a message object and returns a timezone-aware UTC datetime and a UK timezone formatted string."""
    try:
        # Prioritize using the 'received time' (PR_MESSAGE_DELIVERY_TIME) if available, as it's what the user sees in their client.
        if hasattr(msg_obj, 'receivedTime') and msg_obj.receivedTime:
            parsed_dt = msg_obj.receivedTime
        # Fallback to the 'sent time' (PR_CLIENT_SUBMIT_TIME).
        elif hasattr(msg_obj, 'parsedDate') and isinstance(msg_obj.parsedDate, tuple) and len(msg_obj.parsedDate) >= 6:
            parsed_dt = datetime(*msg_obj.parsedDate[:6])
        else:
            # If no usable date is found, raise an error to fall back to timezone.now().
            raise ValueError("No valid date property found in message object")

        # At this point, parsed_dt is a datetime object. We need to ensure it's timezone-aware and then convert to UTC.
        if parsed_dt.tzinfo is None or parsed_dt.tzinfo.utcoffset(parsed_dt) is None:
            # If the datetime is naive, we assume it represents a time in the project's local timezone.
            local_tz = pytz.timezone(settings.TIME_ZONE)
            aware_dt = local_tz.localize(parsed_dt, is_dst=None)
        else:
            # If it's already timezone-aware, we can use it directly.
            aware_dt = parsed_dt

        # Convert the (now definitely aware) datetime to UTC for consistent storage in the database.
        utc_dt = aware_dt.astimezone(pytz.UTC)
        
        # Convert to UK timezone (GMT/BST) for display string
        uk_tz = pytz.timezone('Europe/London')
        uk_dt = utc_dt.astimezone(uk_tz)
        
        # Format with UK timezone abbreviation (GMT/BST)
        tz_name = uk_dt.strftime('%Z')  # Will be 'GMT' or 'BST'
        formatted_date = uk_dt.strftime(f'%b %d, %Y %H:%M {tz_name}')
        
        return utc_dt, formatted_date

    except Exception as e:
        logger.warning(f"Could not parse date from message object: {e}")
    
    # Fallback to the current time in UTC if any of the above fails.
    now_utc = timezone.now() # timezone.now() is already UTC if USE_TZ=True
    
    # Convert to UK timezone for display
    uk_tz = pytz.timezone('Europe/London')
    now_uk = now_utc.astimezone(uk_tz)
    tz_name = now_uk.strftime('%Z')  # Will be 'GMT' or 'BST'
    formatted_date = now_uk.strftime(f'%b %d, %Y %H:%M {tz_name}')
    
    return now_utc, formatted_date


def _remove_banners(text: str) -> str:
    """Removes known warning banners from email text by filtering lines."""
    if not text:
        return ""

    warning_banner1_lower = "WARNING: This email came from outside of the organisation.".lower()
    banner2_start_lower = "You don't often get email from".lower()
    banner2_end_lower = "Learn why this is important".lower()

    cleaned_lines = []
    for line in text.splitlines():
        line_lower = line.lower()
        # Check for banners and skip them
        if warning_banner1_lower in line_lower:
            continue
        if banner2_start_lower in line_lower and banner2_end_lower in line_lower:
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)

def _remove_angle_bracket_links(text: str) -> str:
    """Removes <URL> patterns from text."""
    if not text:
        return ""
    # Regex to find <http://...> or <https://...> patterns
    # It looks for '<', then 'http' or 'https', then '://', then any characters until '>'
    link_pattern = re.compile(r'<https?://[^>]+>')
    return link_pattern.sub('', text)

def _format_plain_text_for_html_display(text: str) -> str:
    """
    Safely converts a plain text string to an HTML string,
    preserving line breaks and styling quoted sections.
    Uses intelligent line break processing to handle real mailbox emails properly.
    """
    if not text:
        return ""

    # 1. Normalize all newline types to a single \n.
    text = re.sub(r'\r\n|\r', '\n', text)
    # 2. Collapse any line containing only horizontal whitespace (spaces, tabs).
    text = re.sub(r'\n[ \t]+\n', '\n', text)

    # 3. ENHANCED: Apply same intelligent line break processing as 'plain' mode
    # Split into lines and intelligently rebuild with proper spacing
    lines = text.split('\n')
    processed_lines = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Add this line to processed lines
        processed_lines.append(line)

        # Look ahead to determine spacing needed
        j = i + 1
        # Skip empty lines to find next content line
        while j < len(lines) and not lines[j].strip():
            j += 1

        if j < len(lines):
            next_line = lines[j].strip()

            # Determine if we need paragraph break or line break
            # Paragraph break indicators:
            # - Current line is very short (like "thanks", "Hi")
            # - Current line ends with punctuation
            # - Next line starts new context (like "From:", names, departments)
            # - Next line is an email header (major email boundary)
            current_is_short = len(line) < 15
            current_ends_punct = line.endswith(('.', '!', '?', ':', ';'))
            next_is_signature_start = (
                re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', next_line) or  # Full names
                'Team' in next_line or 'Department' in next_line or 'Officer' in next_line
            )
            next_is_email_header = re.match(r'^From:', next_line, re.IGNORECASE)

            # Add paragraph break if this looks like end of paragraph
            if (current_is_short and current_ends_punct) or \
               (current_is_short and next_is_signature_start) or \
               (line in ['thanks', 'Thanks', 'regards', 'Regards']):
                processed_lines.append('')  # This creates paragraph break

            # Add single paragraph break before new email blocks (From: headers)
            if next_is_email_header:
                processed_lines.append('')  # Single paragraph break for email boundaries

        i = j if j < len(lines) else len(lines)

    # Now convert to HTML with proper paragraph/line break structure
    # Escape HTML first
    escaped_lines = [html.escape(line) for line in processed_lines]

    # Process for HTML display
    html_lines = []
    reply_header_pattern = re.compile(r"^\s*(&gt;\s*)*(From|Sent|To|Subject|Date|Original Message|Forwarded message):", re.IGNORECASE)
    dash_separator_pattern = re.compile(r"^\s*(-{5,}|_{5,})\s*$")

    for i, line in enumerate(escaped_lines):
        # Add <hr> if a reply header is found, but not for the very first few lines
        if i > 2 and (reply_header_pattern.match(line) or dash_separator_pattern.match(line)):
            # Check if the previous line was blank, indicating a stronger boundary
            if html_lines and not html_lines[-1].strip():
                html_lines.append('<hr>')
        html_lines.append(line)

    # Join with <br> tags, but empty lines become paragraph breaks
    final_parts = []
    current_paragraph = []

    for line in html_lines:
        if line == '':  # Empty line = paragraph break
            if current_paragraph:
                final_parts.append('<br>'.join(current_paragraph))
                current_paragraph = []
        else:
            current_paragraph.append(line)

    # Add final paragraph
    if current_paragraph:
        final_parts.append('<br>'.join(current_paragraph))

    # Join paragraphs with double <br> tags
    html_with_breaks = '<br><br>'.join(final_parts)

    # 4. Find and wrap quoted sections. The regex now operates on the safe HTML string.
    def wrap_quotes(match):
        block = match.group(1)
        lines = block.split('<br>')
        unquoted_lines = []
        for line in lines:
            if line.startswith('&gt; '):
                unquoted_lines.append(line[5:])
            elif line.startswith('&gt;'):
                unquoted_lines.append(line[4:])
            else:
                unquoted_lines.append(line)
        unquoted_block = '<br>'.join(unquoted_lines)
        return f'<div class="email-quote">{unquoted_block}</div>'

    quote_pattern = re.compile(r'((?:^&gt;.*(?:<br>|$))+)', re.MULTILINE)
    final_html = quote_pattern.sub(wrap_quotes, html_with_breaks)
    return final_html


def _resize_image_if_needed(image_data, max_size_mb=2, max_dimension=2048, quality=85):
    """
    Resize image if it's too large, maintaining aspect ratio.
    Requires Pillow (PIL) to be installed. Falls back gracefully if not available.

    Args:
        image_data: Raw image bytes
        max_size_mb: Maximum file size in MB before resizing
        max_dimension: Maximum width or height in pixels
        quality: JPEG quality (1-100)

    Returns:
        Tuple of (resized_image_data, was_resized, new_size)
    """
    try:
        # Try to import PIL - if not available, return original image
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow (PIL) not installed - image resizing disabled. Install with: pip install Pillow")
            return image_data, False, len(image_data)

        original_size = len(image_data)
        max_size_bytes = max_size_mb * 1024 * 1024

        # If image is under the size limit, return as-is
        if original_size <= max_size_bytes:
            return image_data, False, original_size

        logger.info(f"Image size {original_size:,} bytes exceeds {max_size_mb}MB limit, resizing...")

        # Open image with PIL
        image = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (for JPEG output)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparent images
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # Calculate new dimensions maintaining aspect ratio
        width, height = image.size
        if width > max_dimension or height > max_dimension:
            if width > height:
                new_width = max_dimension
                new_height = int((height * max_dimension) / width)
            else:
                new_height = max_dimension
                new_width = int((width * max_dimension) / height)

            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"Resized image dimensions from {width}x{height} to {new_width}x{new_height}")

        # Save as JPEG with specified quality
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        resized_data = output.getvalue()

        logger.info(f"Image resized from {original_size:,} bytes to {len(resized_data):,} bytes ({(len(resized_data)/original_size)*100:.1f}% of original)")
        return resized_data, True, len(resized_data)

    except Exception as e:
        logger.error(f"Error resizing image: {e}", exc_info=True)
        # Return original data if resizing fails
        return image_data, False, len(image_data)


def _extract_image_attachments(msg_obj):
    """
    Extract image and document attachments from an email message and save them temporarily.
    Automatically resizes large images to optimize storage.

    Args:
        msg_obj: extract_msg.Message object

    Returns:
        List of dictionaries containing attachment information (images and documents)
    """

    attachments = []

    if not msg_obj.attachments:
        return attachments

    # Define file extensions we want to extract
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    document_extensions = {'.pdf', '.doc', '.docx'}

    try:
        # Create temporary directories for email attachments with date structure
        today = timezone.now().date()
        
        for attachment in msg_obj.attachments:
            try:
                # Get attachment filename
                filename = getattr(attachment, 'longFilename', None) or getattr(attachment, 'shortFilename', 'unknown')
                file_ext = os.path.splitext(filename.lower())[1]
                
                # Check if it's a supported file type
                is_image = file_ext in image_extensions
                is_document = file_ext in document_extensions
                
                if not (is_image or is_document):
                    continue

                # Get attachment data
                attachment_data = attachment.data
                if not attachment_data:
                    continue

                # Determine file type and processing
                if is_image:
                    # Create image directory
                    temp_dir = os.path.join(settings.MEDIA_ROOT, 'enquiry_photos', 
                                          today.strftime('%Y'), today.strftime('%m'), today.strftime('%d'))
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    # Resize image if needed
                    processed_data, was_resized, final_size = _resize_image_if_needed(attachment_data)

                    # Generate unique filename - use .jpg for resized images
                    if was_resized and file_ext.lower() not in ['.jpg', '.jpeg']:
                        unique_filename = f"{uuid.uuid4()}.jpg"
                    else:
                        unique_filename = f"{uuid.uuid4()}{file_ext}"
                    
                    file_type = 'image'
                else:  # is_document
                    # Create document directory
                    temp_dir = os.path.join(settings.MEDIA_ROOT, 'enquiry_attachments', 'documents',
                                          today.strftime('%Y'), today.strftime('%m'), today.strftime('%d'))
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    # No processing needed for documents
                    processed_data = attachment_data
                    was_resized = False
                    final_size = len(attachment_data)
                    unique_filename = f"{uuid.uuid4()}{file_ext}"
                    file_type = 'document'

                file_path = os.path.join(temp_dir, unique_filename)

                # Save the processed data
                with open(file_path, 'wb') as f:
                    f.write(processed_data)

                # Calculate relative path from MEDIA_ROOT
                relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT).replace('\\', '/')

                attachment_info = {
                    'original_filename': filename,
                    'saved_filename': unique_filename,
                    'file_path': relative_path,
                    'file_size': final_size,
                    'file_url': f"{settings.MEDIA_URL}{relative_path}",
                    'file_type': file_type,
                    'upload_type': 'extracted'  # Mark as extracted from email
                }
                
                # Add image-specific info
                if is_image:
                    attachment_info.update({
                        'was_resized': was_resized,
                        'original_size': len(attachment_data) if was_resized else final_size
                    })

                attachments.append(attachment_info)

                resize_info = f" (resized from {len(attachment_data):,} bytes)" if was_resized else ""
                logger.info(f"Extracted {file_type} attachment: {filename} -> {relative_path}{resize_info}")

            except Exception as e:
                logger.error(f"Error extracting attachment {filename}: {e}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Error creating attachment directory or processing attachments: {e}", exc_info=True)

    return attachments


def parse_msg_file(file_path, body_content_mode='snippet', skip_attachments=False):
    """
    Parses an Outlook .msg file by orchestrating helper functions.

    Args:
        file_path: Path to the .msg file
        body_content_mode: 'snippet' for latest email only, 'full' for complete conversation
        skip_attachments: If True, skip processing attachments (useful for history updates)

    Returns:
        Dictionary with email data or error information
    """
    logger.info(f"=== EMAIL PARSING DEBUG START ===")
    logger.info(f"Parsing mode: {body_content_mode}, Skip attachments: {skip_attachments}")
    logger.info(f"File path: {file_path}")
    try:
        msg_obj = extract_msg.Message(file_path)
    except Exception as e_open:
        logger.error(f"Failed to open or parse .msg file at {file_path}: {e_open}", exc_info=True)
        return {'error': f"Failed to open/parse .msg file: {e_open}"}

    try:
        # --- Sender & Recipient Parsing ---
        email_from, raw_from = _parse_sender_info(msg_obj)

        # --- Date, Body, and Attachment Parsing ---
        email_date, email_date_str = _parse_email_date(msg_obj)

        is_html_native = bool(getattr(msg_obj, 'html_body', None))
        plain_text_body = msg_obj.body or ""

        # DEBUG: Log raw email content structure
        logger.info(f"Email content analysis:")
        logger.info(f"  - has_html_body: {is_html_native}")
        logger.info(f"  - plain_text_body length: {len(plain_text_body)}")
        logger.info(f"  - plain_text_body preview (first 200 chars): {repr(plain_text_body[:200])}")
        if is_html_native:
            html_body = getattr(msg_obj, 'html_body', '')
            logger.info(f"  - html_body length: {len(html_body)}")
            logger.info(f"  - html_body preview (first 200 chars): {repr(html_body[:200])}")

        # Determine direction from multiple sources for better accuracy
        direction = 'OUTGOING'  # Default assumption

        # Method 1: Check email addresses (TO and CC fields)
        member_enquiries_email = 'memberenquiries@redcar-cleveland.gov.uk'

        # Check TO field
        if msg_obj.to:
            to_addresses = _format_recipient_list(msg_obj.to).lower()
            if member_enquiries_email in to_addresses:
                direction = 'INCOMING'  # Email TO memberenquiries = incoming

        # Check CC field if not already detected as incoming
        if direction == 'OUTGOING' and msg_obj.cc:
            cc_addresses = _format_recipient_list(msg_obj.cc).lower()
            if member_enquiries_email in cc_addresses:
                direction = 'INCOMING'  # Email CC'd to memberenquiries = incoming

        # Check BCC field if not already detected as incoming (less common but thorough)
        if direction == 'OUTGOING' and hasattr(msg_obj, 'bcc') and msg_obj.bcc:
            bcc_addresses = _format_recipient_list(msg_obj.bcc).lower()
            if member_enquiries_email in bcc_addresses:
                direction = 'INCOMING'  # Email BCC'd to memberenquiries = incoming

        if direction == 'OUTGOING' and raw_from:
            from_address = raw_from.lower()
            if member_enquiries_email in from_address:
                direction = 'OUTGOING'  # Email FROM memberenquiries = outgoing

        # Method 2: Check warning banners (fallback for unclear cases)
        if direction == 'OUTGOING':  # Only check banners if email direction is still unclear
            warning_banner1 = "WARNING: This email came from outside of the organisation. Do not provide login or password details. Always be cautious opening links and attachments wherever the email appears to come from. If you have any doubts about this email, contact ICT."
            banner2_pattern = re.compile(r"You don't often get email from [\s\S]+?\. Learn why this is important\.", re.IGNORECASE)
            if warning_banner1 in plain_text_body[:400] or banner2_pattern.search(plain_text_body[:400]):
                direction = 'INCOMING'

        # --- Determine final body content and is_html flag ---
        if body_content_mode == 'snippet':
            cleaned_plain = _remove_banners(plain_text_body)
            # Use the same robust newline normalization as the full view.
            text = re.sub(r'\r\n|\r', '\n', cleaned_plain)
            text = re.sub(r'\n[ \t]+\n', '\n', text)
            normalized_snippet = re.sub(r'\n{3,}', '\n\n', text)

            # Also strip leading whitespace from the final snippet to prevent phantom spacing
            body_content = (normalized_snippet[:247] + '...' if len(normalized_snippet) > 250 else normalized_snippet).lstrip()
            is_html_for_frontend = False

            # DEBUG: Log snippet processing result
            logger.info(f"SNIPPET mode result:")
            logger.info(f"  - final body_content length: {len(body_content)}")
            logger.info(f"  - final body_content preview: {repr(body_content[:200])}")
            logger.info(f"  - is_html_for_frontend: {is_html_for_frontend}")
        elif body_content_mode == 'plain':
            # Plain text mode for history notes - full content, properly formatted plain text
            cleaned_plain = _remove_banners(plain_text_body)
            # Normalize line endings and clean up excessive spacing
            text = re.sub(r'\r\n|\r', '\n', cleaned_plain)
            text = re.sub(r'\n[ \t]+\n', '\n', text)

            # ENHANCED: Fix excessive double line breaks from real mailbox emails
            # Split into lines and intelligently rebuild with proper spacing
            lines = text.split('\n')
            processed_lines = []

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Skip empty lines
                if not line:
                    i += 1
                    continue

                # Add this line to processed lines
                processed_lines.append(line)

                # Look ahead to determine spacing needed
                j = i + 1
                # Skip empty lines to find next content line
                while j < len(lines) and not lines[j].strip():
                    j += 1

                if j < len(lines):
                    next_line = lines[j].strip()

                    # Determine if we need paragraph break or line break
                    # Paragraph break indicators:
                    # - Current line is very short (like "thanks", "Hi")
                    # - Current line ends with punctuation
                    # - Next line starts new context (like "From:", names, departments)
                    # - Next line is an email header (major email boundary)
                    current_is_short = len(line) < 15
                    current_ends_punct = line.endswith(('.', '!', '?', ':', ';'))
                    next_is_signature_start = (
                        re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', next_line) or  # Full names
                        'Team' in next_line or 'Department' in next_line or 'Officer' in next_line
                    )
                    next_is_email_header = re.match(r'^From:', next_line, re.IGNORECASE)

                    # Add paragraph break if this looks like end of paragraph
                    if (current_is_short and current_ends_punct) or \
                       (current_is_short and next_is_signature_start) or \
                       (line in ['thanks', 'Thanks', 'regards', 'Regards']):
                        processed_lines.append('')  # This creates paragraph break

                    # Add single paragraph break before new email blocks (From: headers)
                    if next_is_email_header:
                        processed_lines.append('')  # Single paragraph break for email boundaries

                i = j if j < len(lines) else len(lines)

            # Join with single line breaks, then paragraph breaks will be double
            body_content = '\n'.join(processed_lines).strip()
            # Final cleanup - ensure no more than double line breaks
            body_content = re.sub(r'\n{3,}', '\n\n', body_content)
            is_html_for_frontend = False

            # DEBUG: Log plain processing result
            logger.info(f"PLAIN mode result:")
            logger.info(f"  - final body_content length: {len(body_content)}")
            logger.info(f"  - final body_content preview: {repr(body_content[:200])}")
            logger.info(f"  - is_html_for_frontend: {is_html_for_frontend}")
        else: # 'full' mode
            is_html_for_frontend = True # Full view is now always HTML
            if is_html_native:
                body_content = _remove_banners(msg_obj.html_body)
            else:
                cleaned_plain_banners = _remove_banners(plain_text_body)
                cleaned_plain_links = _remove_angle_bracket_links(cleaned_plain_banners)
                body_content = _format_plain_text_for_html_display(cleaned_plain_links)

            # DEBUG: Log full processing result
            logger.info(f"FULL mode result:")
            logger.info(f"  - used html_body: {is_html_native}")
            logger.info(f"  - final body_content length: {len(body_content)}")
            logger.info(f"  - final body_content preview: {repr(body_content[:200])}")
            logger.info(f"  - is_html_for_frontend: {is_html_for_frontend}")

        # --- Extract Image and Document Attachments ---
        # Skip attachment processing for history updates to avoid failures
        if skip_attachments:
            attachments = []
            logger.info("Skipping attachment processing as requested")
        else:
            attachments = _extract_image_attachments(msg_obj)  # Function now handles both images and documents

        parsed_data = {
            'raw_from': raw_from,
            'email_from': email_from,
            'email_to': _format_recipient_list(msg_obj.to) or "Unknown Recipient(s)",
            'email_cc': _format_recipient_list(msg_obj.cc),
            'subject': msg_obj.subject or "(No Subject)",
            'email_date': email_date,
            'email_date_str': email_date_str,
            'body_content': body_content or "(No body content)",
            'direction': direction,
            'has_attachments': bool(msg_obj.attachments),
            'is_html': is_html_for_frontend,
            'image_attachments': attachments,  # Now contains both images and documents
        }

        # DEBUG: Log final parsed data structure
        logger.info(f"Final parsed_data keys: {list(parsed_data.keys())}")
        logger.info(f"Final body_content length: {len(parsed_data.get('body_content', ''))}")
        logger.info(f"Final is_html: {parsed_data.get('is_html', False)}")
        logger.info(f"=== EMAIL PARSING DEBUG END ===")

        return parsed_data

    except Exception as e_parse:
        logger.error(f"Error during .msg file processing after opening {file_path}: {e_parse}", exc_info=True)
        return {'error': f"General error processing .msg file: {e_parse}"}
    
    finally:
        if 'msg_obj' in locals() and msg_obj:
            msg_obj.close()


def create_enquiry_from_email(parsed_email_data, created_by_user):
    """
    Creates an enquiry from parsed email data.

    Args:
        parsed_email_data: Dictionary containing parsed email information
        created_by_user: User object who is creating the enquiry

    Returns:
        Dictionary with 'success' boolean and either 'enquiry' object or 'error' message
    """
    # Import models locally if not available at module level
    EnquiryModel = Enquiry
    EnquiryHistoryModel = EnquiryHistory  
    MemberModel = Member
    if EnquiryModel is None:
        from .models import Enquiry as EnquiryModel, EnquiryHistory as EnquiryHistoryModel, Member as MemberModel

    try:
        # Extract sender email address
        sender_email = ""
        if parsed_email_data.get('email_from'):
            _, sender_email = parseaddr(parsed_email_data['email_from'])

        if not sender_email:
            return {
                'success': False,
                'error': 'Could not extract sender email address from email'
            }

        # Try to find a member by email address
        try:
            member = MemberModel.objects.get(email__iexact=sender_email, is_active=True)
        except MemberModel.DoesNotExist:
            return {
                'success': False,
                'error': f'No active member found with email address: {sender_email}'
            }
        except MemberModel.MultipleObjectsReturned:
            # If multiple members have the same email, get the first active one
            member = MemberModel.objects.filter(email__iexact=sender_email, is_active=True).first()
            if not member:
                return {
                    'success': False,
                    'error': f'Multiple members found with email address: {sender_email}, but none are active'
                }

        # Create the enquiry
        enquiry = EnquiryModel.objects.create(
            title=parsed_email_data.get('subject', 'Email Enquiry')[:255],  # Truncate to field limit
            description=parsed_email_data.get('body_content', 'No content available'),
            member=member,
            reference=EnquiryModel.generate_reference(),
            status='new'
        )

        # Create initial history entry
        EnquiryHistoryModel.objects.create(
            enquiry=enquiry,
            note=f'Enquiry created from email sent on {parsed_email_data.get("email_date_str", "unknown date")}',
            created_by=created_by_user
        )

        return {
            'success': True,
            'enquiry': enquiry,
            'member': member
        }

    except Exception as e:
        logger.error(f"Error creating enquiry from email: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Error creating enquiry: {str(e)}'
        }





def clear_all_session_cache(request):
    """
    Clear all cached data from session.
    Useful for testing or when you want to force refresh of all cached data.
    """
    keys_to_remove = [key for key in request.session.keys() if key.startswith('merge_confirm_')]
    for key in keys_to_remove:
        del request.session[key]


class DateRangeUtility:
    """Unified date range utility for both reports and enquiry filtering."""
    
    @staticmethod
    def generate_month_periods(count=12):
        """
        Generate month periods using proper date arithmetic.
        
        Args:
            count: Number of months to generate (default 12)
            
        Returns:
            Tuple of (months_list, month_keys_list, date_from, date_to) where:
            - months_list: ['Dec 2024', 'Nov 2024', ...]
            - month_keys_list: ['2024-12', '2024-11', ...]
            - date_from: Start of first month (timezone-aware)
            - date_to: End of last month (timezone-aware)
        """
        current_date = timezone.now()
        months = []
        month_keys = []
        
        # Use proper month arithmetic instead of day approximation
        for i in range(count - 1, -1, -1):
            # Calculate exact month by going back i months
            year = current_date.year
            month = current_date.month - i
            
            # Handle year rollover
            while month <= 0:
                month += 12
                year -= 1
                
            month_date = current_date.replace(year=year, month=month, day=1)
            months.append(month_date.strftime('%b %Y'))
            month_keys.append(month_date.strftime('%Y-%m'))
        
        # Calculate precise date range
        if month_keys:
            date_from, date_to = DateRangeUtility.calculate_range_from_keys(month_keys)
        else:
            date_from = date_to = timezone.now()
            
        return months, month_keys, date_from, date_to
    
    @staticmethod
    def calculate_range_from_keys(month_keys):
        """
        Calculate precise date range from month keys.
        
        Args:
            month_keys: List of month keys in format ['2024-01', '2024-02', ...]
            
        Returns:
            Tuple of (date_from, date_to) as timezone-aware datetime objects
        """
        if not month_keys:
            return None, None
        
        # First month start date
        first_year, first_month = month_keys[0].split('-')
        date_from = timezone.make_aware(datetime(int(first_year), int(first_month), 1))
        
        # Last month end date (first day of next month)
        last_year, last_month = month_keys[-1].split('-')
        if int(last_month) == 12:
            date_to = timezone.make_aware(datetime(int(last_year) + 1, 1, 1))
        else:
            date_to = timezone.make_aware(datetime(int(last_year), int(last_month) + 1, 1))
        
        return date_from, date_to
    
    @staticmethod
    def get_filter_dates(period_type, custom_from=None, custom_to=None):
        """
        Get date range for enquiry filtering - compatible with EnquiryFilterMixin.

        Args:
            period_type: '3months', '6months', '12months', 'all', or 'custom'
            custom_from: Custom start date (for 'custom' type)
            custom_to: Custom end date (for 'custom' type)

        Returns:
            Tuple of (date_from, date_to) or (None, None) for 'all'
        """
        # Delegate to centralized service
        from .date_range_service import DateRangeService
        return DateRangeService.get_filter_dates(period_type, custom_from, custom_to)


# Backward compatibility functions - delegate to DateRangeUtility
def generate_last_months(count=12):
    """Generate list of months for reports - uses DateRangeUtility."""
    months, month_keys, _, _ = DateRangeUtility.generate_month_periods(count)
    return months, month_keys


def calculate_month_range_from_keys(month_keys):
    """Calculate date range from month keys - uses DateRangeUtility."""
    return DateRangeUtility.calculate_range_from_keys(month_keys)


def validate_file_security(file_data, allowed_extensions=None, max_size_mb=10, check_mime=True):
    """
    Comprehensive file upload security validation.
    
    Args:
        file_data: File data (bytes or file-like object)
        allowed_extensions: Set of allowed extensions (e.g., {'.jpg', '.png'})
        max_size_mb: Maximum file size in MB
        check_mime: Whether to validate MIME type matches extension
        
    Returns:
        Dict with 'valid': bool, 'error': str (if invalid), 'mime_type': str
        
    Raises:
        ValueError: If file fails security validation
    """
    
    if hasattr(file_data, 'read'):
        # File-like object
        file_size = file_data.size if hasattr(file_data, 'size') else len(file_data.read())
        filename = getattr(file_data, 'name', 'unknown')
        if hasattr(file_data, 'seek'):
            file_data.seek(0)  # Reset file pointer
    else:
        # Bytes data
        file_size = len(file_data)
        filename = 'uploaded_file'
    
    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        raise ValueError(f"File size {file_size:,} bytes exceeds {max_size_mb}MB limit")
    
    # Check extension if provided
    if allowed_extensions:
        file_ext = os.path.splitext(filename.lower())[1]
        if file_ext not in allowed_extensions:
            raise ValueError(f"File extension '{file_ext}' not allowed. Allowed: {', '.join(allowed_extensions)}")
    
    # Basic MIME type validation
    mime_type = mimetypes.guess_type(filename)[0]
    if check_mime and allowed_extensions:
        # Define expected MIME types for common extensions
        mime_mapping = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.gif': 'image/gif',
            '.pdf': 'application/pdf', '.txt': 'text/plain',
            '.msg': 'application/vnd.ms-outlook',
            '.eml': 'message/rfc822'
        }
        
        file_ext = os.path.splitext(filename.lower())[1]
        if file_ext in mime_mapping:
            expected_mime = mime_mapping[file_ext]
            if mime_type and not mime_type.startswith(expected_mime.split('/')[0]):
                logger.warning(f"MIME type mismatch: expected {expected_mime}, got {mime_type}")
    
    return {
        'valid': True,
        'mime_type': mime_type,
        'size': file_size,
        'extension': os.path.splitext(filename.lower())[1]
    }


def safe_file_path_join(*paths):
    """
    Safely join file paths preventing directory traversal attacks while allowing legitimate media paths.
    
    Args:
        *paths: Path components to join
        
    Returns:
        Sanitized path string
        
    Raises:
        ValueError: If path contains dangerous sequences
    """
    
    # Convert paths to strings and normalize
    str_paths = [str(path) for path in paths if path]
    
    if not str_paths:
        raise ValueError("No valid paths provided")
    
    # Join the paths first to get the final result
    result_path = os.path.join(*str_paths)
    
    # Now validate the final result path for security issues
    normalized = os.path.normpath(result_path)
    
    # Check for null bytes (most critical security issue)
    if '\x00' in result_path:
        raise ValueError(f"Null byte in path: {result_path}")
    
    # Check for directory traversal attempts - look for '..' as separate path component
    path_parts = normalized.split(os.sep)
    if '..' in path_parts:
        raise ValueError(f"Directory traversal attempt detected: {result_path}")
    
    # Check for dangerous command injection patterns in the complete path
    dangerous_patterns = [
        '|',            # Pipe operator
        ';',            # Command separator  
        '&',            # Background process
        '`',            # Command substitution
        '$(',           # Command substitution
        '${',           # Variable substitution
    ]
    
    for pattern in dangerous_patterns:
        if pattern in result_path:
            raise ValueError(f"Dangerous pattern '{pattern}' detected in path: {result_path}")
    
    # For the first path component (base path like MEDIA_ROOT), allow absolute paths
    # For subsequent components (relative paths), they should be relative
    if len(str_paths) > 1:
        for i, path in enumerate(str_paths[1:], 1):  # Skip first path (base)
            path_normalized = os.path.normpath(path)
            
            # Check if any non-base path component is absolute
            if (path_normalized.startswith('/') or 
                (len(path_normalized) > 1 and path_normalized[1] == ':')):
                raise ValueError(f"Absolute path not allowed for component {i}: {path}")
    
    return result_path


def admin_required(redirect_url='application:index', error_message=None):
    """
    Decorator to require admin permissions for a view.
    
    Args:
        redirect_url: URL name to redirect to if not admin (default: 'application:index')
        error_message: Custom error message (default: standard message)
        
    Usage:
        @admin_required()
        def my_view(request):
            ...
            
        @admin_required(redirect_url='application:welcome', error_message='Custom message')
        def my_view(request):
            ...
    """
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Import Admin locally if not available at module level
            AdminModel = Admin
            if AdminModel is None:
                from .models import Admin as AdminModel
            
            try:
                AdminModel.objects.get(user=request.user)
                return view_func(request, *args, **kwargs)
            except AdminModel.DoesNotExist:
                message = error_message or 'You must be an administrator to access this page. Please contact your system administrator.'
                messages.error(request, message)
                return redirect(redirect_url)
        
        return wrapper
    return decorator


def strip_html_tags(text):
    """
    Remove HTML tags from text while preserving content.
    
    Args:
        text: String that may contain HTML tags
        
    Returns:
        String with HTML tags removed and entities decoded
    """
    if not text:
        return text
    
    import re
    
    # Remove HTML tags but preserve content
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Clean up whitespace - replace multiple spaces/newlines with single ones
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()


def get_text_diff(old_text, new_text, max_length=200):
    """
    Generate a concise diff showing what was added/removed between two texts.
    
    Args:
        old_text: Original text
        new_text: Modified text  
        max_length: Maximum length for each added/removed section
        
    Returns:
        String describing the changes, or None if texts are identical
    """
    if not old_text:
        old_text = ""
    if not new_text:
        new_text = ""
    
    # Strip HTML from both texts for comparison
    old_clean = strip_html_tags(old_text)
    new_clean = strip_html_tags(new_text)
    
    if old_clean == new_clean:
        return None
    
    # Split into words for better diff granularity
    old_words = old_clean.split()
    new_words = new_clean.split()
    
    # Simple word-based diff algorithm
    import difflib
    
    diff = list(difflib.unified_diff(old_words, new_words, lineterm=''))
    
    if not diff:
        return None
    
    added_words = []
    removed_words = []
    
    for line in diff[2:]:  # Skip the header lines
        if line.startswith('+'):
            added_words.extend(line[1:].split())
        elif line.startswith('-'):
            removed_words.extend(line[1:].split())
    
    changes = []
    
    if removed_words:
        removed_text = ' '.join(removed_words)
        if len(removed_text) > max_length:
            removed_text = removed_text[:max_length] + '...'
        changes.append(f"Removed: '{removed_text}'")
    
    if added_words:
        added_text = ' '.join(added_words)
        if len(added_text) > max_length:
            added_text = added_text[:max_length] + '...'
        changes.append(f"Added: '{added_text}'")
    
    if changes:
        return ' | '.join(changes)
    
    # Fallback for cases where diff doesn't capture the change well
    return "Description modified"


def create_json_response(success, data=None, error=None, message=None, **kwargs):
    """
    Create standardized JSON response for API endpoints.

    Args:
        success: Boolean indicating success/failure
        data: Data to include in successful response
        error: Error message for failed response
        message: Success message for successful response
        **kwargs: Additional fields to include in response

    Returns:
        JsonResponse object

    Usage:
        return create_json_response(True, data={'member': member_info})
        return create_json_response(False, error='Member not found')
        return create_json_response(True, message='Operation completed', count=10)
    """

    response_data = {'success': success}

    if success:
        if message:
            response_data['message'] = message
            response_data['message_type'] = 'success'
        if data is not None:
            if isinstance(data, dict):
                response_data.update(data)
            else:
                response_data['data'] = data
        response_data.update(kwargs)
    else:
        response_data['error'] = error or 'An error occurred'
        response_data['message_type'] = 'error'

    return JsonResponse(response_data)


# Date calculation utilities
def calculate_business_days(start_date, end_date):
    """
    Calculate business days between two dates (excluding weekends).

    Args:
        start_date: Start date (datetime or date object)
        end_date: End date (datetime or date object)

    Returns:
        Number of business days as integer, or None if calculation fails
    """
    try:
        if not start_date or not end_date:
            return None

        # Convert to date objects if they're datetime
        if hasattr(start_date, 'date'):
            start_date = start_date.date()
        if hasattr(end_date, 'date'):
            end_date = end_date.date()

        business_days = 0
        current_date = start_date

        while current_date < end_date:
            # Monday = 0, Sunday = 6
            if current_date.weekday() < 5:  # Monday to Friday
                business_days += 1
            current_date += timedelta(days=1)

        return business_days
    except (TypeError, AttributeError):
        return None


def calculate_calendar_days(start_date, end_date):
    """
    Calculate calendar days between two dates.

    Args:
        start_date: Start date (datetime or date object)
        end_date: End date (datetime or date object)

    Returns:
        Number of calendar days as integer, or None if calculation fails
    """
    try:
        if not start_date or not end_date:
            return None

        # Convert to date objects if they're datetime
        if hasattr(start_date, 'date'):
            start_date = start_date.date()
        if hasattr(end_date, 'date'):
            end_date = end_date.date()

        return (end_date - start_date).days
    except (TypeError, AttributeError):
        return None


def calculate_working_days_due_date(start_date, business_days):
    """
    Calculate due date by adding business days to start date.

    Args:
        start_date: Start date (datetime or date object)
        business_days: Number of business days to add

    Returns:
        Due date as date object, or None if calculation fails
    """
    try:
        if not start_date or not business_days:
            return None

        # Convert to date object if it's datetime
        if hasattr(start_date, 'date'):
            current_date = start_date.date()
        else:
            current_date = start_date

        days_added = 0

        while days_added < business_days:
            current_date += timedelta(days=1)
            # Monday = 0, Sunday = 6
            if current_date.weekday() < 5:  # Monday to Friday
                days_added += 1

        return current_date
    except (TypeError, AttributeError):
        return None
