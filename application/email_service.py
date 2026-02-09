"""
Unified Email Processing Service for the Members Enquiries System.

This module consolidates all email processing logic into a single service,
eliminating duplication across views.py, utils.py, and other modules.
"""

import logging
import os
import tempfile
from email.utils import parseaddr
from typing import Dict, Optional, Tuple, Any
from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse
from django.utils import timezone

from .file_security import FileUploadService
from .models import Member
from .utils import parse_msg_file, create_json_response

logger = logging.getLogger(__name__)


class EmailProcessingService:
    """
    Centralized service for all email processing operations.
    
    This service consolidates functionality from:
    - api_parse_email view function
    - api_parse_email_update view function
    - Various email parsing utilities
    - Member lookup by email functionality
    """
    
    # Supported email file extensions
    SUPPORTED_EXTENSIONS = {'.msg', '.eml'}
    
    # Email parsing modes
    PARSING_MODES = {
        'snippet': 'snippet',  # For form population (truncated)
        'full': 'full',        # For HTML display
        'plain': 'plain',      # For plain text (history notes)
        'conversation': 'conversation'  # For conversation extraction
    }
    
    @classmethod
    def validate_email_file(cls, uploaded_file: UploadedFile) -> Dict[str, Any]:
        """
        Validate uploaded email file with comprehensive security checks.
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Returns:
            Dictionary with validation results
        """
        if not uploaded_file:
            return {
                'success': False,
                'error': 'No file provided',
                'error_type': 'missing_file'
            }
        
        # Check file extension
        file_extension = '.' + uploaded_file.name.split('.')[-1].lower()
        if file_extension not in cls.SUPPORTED_EXTENSIONS:
            return {
                'success': False,
                'error': f'Unsupported file type. Please upload {", ".join(cls.SUPPORTED_EXTENSIONS)} files only.',
                'error_type': 'invalid_extension'
            }
        
        # Use centralized file security validation
        try:
            validation_result = FileUploadService.handle_email_upload(uploaded_file)
            if not validation_result["success"]:
                return {
                    'success': False,
                    'error': validation_result["error"],
                    'error_type': validation_result.get('error_type', 'validation')
                }
            
            return {
                'success': True,
                'file_info': validation_result.get('file_info', {}),
                'validated': True
            }
            
        except Exception as e:
            logger.error(f"Email file validation failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"File validation failed: {str(e)}",
                'error_type': 'processing'
            }
    
    @classmethod
    def parse_email_file(cls, uploaded_file: UploadedFile,
                        parsing_mode: str = 'snippet',
                        skip_attachments: bool = False) -> Dict[str, Any]:
        """
        Parse email file with unified error handling and temporary file management.

        Args:
            uploaded_file: Django UploadedFile object
            parsing_mode: 'snippet', 'full', or 'conversation'
            skip_attachments: If True, skip processing attachments (useful for history updates)

        Returns:
            Dictionary with parsed email data or error information
        """
        # Validate file first
        validation_result = cls.validate_email_file(uploaded_file)
        if not validation_result['success']:
            return validation_result
        
        # Validate parsing mode
        if parsing_mode not in cls.PARSING_MODES:
            parsing_mode = 'snippet'
        
        # Create temporary file for processing
        temp_file_path = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.msg') as temp_file:
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Parse the email based on file type
            if uploaded_file.name.lower().endswith('.msg'):
                parsed_data = parse_msg_file(temp_file_path, body_content_mode=parsing_mode, skip_attachments=skip_attachments)
            elif uploaded_file.name.lower().endswith('.eml'):
                # EML parsing not yet implemented - return appropriate error
                return {
                    'success': False,
                    'error': 'EML file parsing not yet implemented. Please use .msg files.',
                    'error_type': 'not_implemented'
                }
            else:
                return {
                    'success': False,
                    'error': 'Unsupported file type',
                    'error_type': 'invalid_extension'
                }
            
            # Check for parsing errors
            if isinstance(parsed_data, dict) and "error" in parsed_data:
                return {
                    'success': False,
                    'error': f'Error parsing email: {parsed_data["error"]}',
                    'error_type': 'parsing_error'
                }
            
            return {
                'success': True,
                'email_data': parsed_data,
                'parsing_mode': parsing_mode
            }
            
        except Exception as e:
            logger.error(f"Error parsing email file: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"Error processing email file: {str(e)}",
                'error_type': 'processing'
            }
        
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")
    
    @classmethod
    def extract_sender_email(cls, email_data: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Extract sender email address from parsed email data.
        
        Args:
            email_data: Parsed email data dictionary
            
        Returns:
            Tuple of (sender_email, success)
        """
        if not email_data or not isinstance(email_data, dict):
            return "", False
        
        # Try to extract from email_from field
        email_from = email_data.get('email_from', '')
        if email_from:
            _, sender_email = parseaddr(email_from)
            if sender_email:
                return sender_email, True
        
        # Try raw_from as fallback
        raw_from = email_data.get('raw_from', '')
        if raw_from:
            _, sender_email = parseaddr(raw_from)
            if sender_email:
                return sender_email, True
        
        return "", False
    
    @classmethod
    def find_member_by_email(cls, email: str) -> Optional[Member]:
        """
        Find an active member by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            Member instance if found, None otherwise
        """
        if not email:
            return None
        
        try:
            return Member.objects.get(email__iexact=email, is_active=True)
        except Member.DoesNotExist:
            return None
        except Member.MultipleObjectsReturned:
            # Return first active member if multiple found
            logger.warning(f"Multiple members found for email {email}, returning first active")
            return Member.objects.filter(email__iexact=email, is_active=True).first()
    
    @classmethod
    def process_email_for_form_population(cls, uploaded_file: UploadedFile) -> JsonResponse:
        """
        Process email file for form population (enquiry creation).
        
        Consolidates logic from api_parse_email view.
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Returns:
            JsonResponse with processed email data
        """
        # Parse email file
        result = cls.parse_email_file(uploaded_file, parsing_mode='full')
        
        if not result['success']:
            return JsonResponse({
                "success": False, 
                "error": result['error']
            })
        
        email_data = result['email_data']
        
        # Extract sender email and find member
        sender_email, email_extracted = cls.extract_sender_email(email_data)
        
        if not email_extracted:
            return JsonResponse({
                "success": False,
                "error": "Could not extract sender email address from email"
            })
        
        # Find member by email
        member = cls.find_member_by_email(sender_email)
        
        # Prepare response data in the format expected by frontend
        response_data = {
            "success": True,
            "data": {
                "subject": email_data.get("subject", ""),
                "body_content": email_data.get("body_content", ""),
                "sender_email": sender_email,
                "email_from": email_data.get("email_from", ""),
                "email_to": email_data.get("email_to", ""),
                "email_cc": email_data.get("email_cc", ""),
                "email_date": email_data.get("email_date_str", ""),
                "image_attachments": email_data.get("image_attachments", []),
            },
            "sender_email": sender_email,
            "member_found": member is not None,
        }
        
        # Add member information if found
        if member:
            response_data["member_info"] = {
                "id": member.id,
                "name": member.full_name,
                "email": member.email,
                "ward": member.ward.name if member.ward else "Unknown",
            }
        
        return JsonResponse(response_data)
    
    @classmethod
    def process_email_for_history(cls, uploaded_file: UploadedFile) -> JsonResponse:
        """
        Process email file for enquiry history updates.

        Consolidates logic from api_parse_email_update view.

        Args:
            uploaded_file: Django UploadedFile object

        Returns:
            JsonResponse with processed email data for history
        """
        # Parse email file with plain text mode for history - we want full plain text, not HTML
        result = cls.parse_email_file(uploaded_file, parsing_mode='plain', skip_attachments=True)
        
        if not result['success']:
            return JsonResponse({
                "success": False, 
                "error": result['error']
            })
        
        email_data = result['email_data']
        
        # Use existing EmailProcessingService for history processing
        from .services import EmailProcessingService as LegacyEmailService
        processed_email = LegacyEmailService.process_email_for_history(email_data)
        
        return JsonResponse({
            "success": True, 
            "email_data": processed_email
        })
