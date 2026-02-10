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
Unified Message Service for the Members Enquiries System.

This module consolidates all message display logic into a single service,
ensuring consistent message delivery across the application.
"""

from typing import Dict, Optional, Any
from django.contrib import messages
from django.http import JsonResponse


class MessageService:
    """
    Centralized service for all message display operations.
    
    This service consolidates functionality from:
    - Django messages framework (used for login/logout)
    - JavaScript alert systems (used for errors)
    - Toast notifications (preferred method)
    - JSON response messages (for AJAX calls)
    
    All messages will be delivered via the toast notification system
    for consistent user experience.
    """
    
    # Message type mappings
    MESSAGE_TYPES = {
        'success': 'success',
        'error': 'error',
        'danger': 'error',  # Bootstrap danger -> error
        'warning': 'warning',
        'info': 'info',
        'debug': 'info',  # Debug -> info
    }
    
    @classmethod
    def add_message(cls, request, message_type: str, message: str, 
                   extra_tags: str = '') -> None:
        """
        Add a message using Django's messages framework.
        
        This will be automatically converted to a toast notification
        by the base template.
        
        Args:
            request: Django request object
            message_type: Type of message (success, error, warning, info)
            message: Message text
            extra_tags: Additional tags for the message
        """
        # Normalize message type
        normalized_type = cls.MESSAGE_TYPES.get(message_type, 'info')
        
        # Map to Django message levels
        level_map = {
            'success': messages.SUCCESS,
            'error': messages.ERROR,
            'warning': messages.WARNING,
            'info': messages.INFO,
        }
        
        level = level_map.get(normalized_type, messages.INFO)
        
        # Add message with normalized type as tag
        messages.add_message(
            request, 
            level, 
            message, 
            extra_tags=f"{normalized_type} {extra_tags}".strip()
        )
    
    @classmethod
    def success(cls, request, message: str, extra_tags: str = '') -> None:
        """Add a success message."""
        cls.add_message(request, 'success', message, extra_tags)
    
    @classmethod
    def error(cls, request, message: str, extra_tags: str = '') -> None:
        """Add an error message."""
        cls.add_message(request, 'error', message, extra_tags)
    
    @classmethod
    def warning(cls, request, message: str, extra_tags: str = '') -> None:
        """Add a warning message."""
        cls.add_message(request, 'warning', message, extra_tags)
    
    @classmethod
    def info(cls, request, message: str, extra_tags: str = '') -> None:
        """Add an info message."""
        cls.add_message(request, 'info', message, extra_tags)
    
    @classmethod
    def create_json_response(cls, success: bool, message: str = '', 
                           error: str = '', data: Optional[Dict] = None,
                           message_type: str = 'info') -> JsonResponse:
        """
        Create a standardized JSON response with message information.
        
        This ensures AJAX responses can also trigger toast notifications
        on the frontend.
        
        Args:
            success: Whether the operation was successful
            message: Success message (if success=True)
            error: Error message (if success=False)
            data: Additional data to include in response
            message_type: Type of message for frontend display
            
        Returns:
            JsonResponse with standardized format
        """
        response_data = {
            'success': success,
        }
        
        if success:
            if message:
                response_data['message'] = message
                response_data['message_type'] = 'success'
            if data:
                response_data.update(data)
        else:
            response_data['error'] = error or 'An error occurred'
            response_data['message_type'] = 'error'
        
        # Add message type for frontend toast display
        if 'message_type' not in response_data:
            response_data['message_type'] = cls.MESSAGE_TYPES.get(message_type, 'info')
        
        return JsonResponse(response_data)
    
    @classmethod
    def create_success_response(cls, message: str = '', data: Optional[Dict] = None) -> JsonResponse:
        """Create a success JSON response."""
        return cls.create_json_response(True, message=message, data=data)
    
    @classmethod
    def create_error_response(cls, error: str, data: Optional[Dict] = None) -> JsonResponse:
        """Create an error JSON response."""
        return cls.create_json_response(False, error=error, data=data)
    
    @classmethod
    def get_javascript_config(cls) -> Dict[str, Any]:
        """
        Get configuration for JavaScript message handling.
        
        Returns configuration that can be used to ensure
        JavaScript code uses the same message types and styling.
        """
        return {
            'message_types': cls.MESSAGE_TYPES,
            'default_options': {
                'autohide': True,
                'delay': 5000,
                'position': 'top-end',  # Toast position
            },
            'type_config': {
                'success': {
                    'icon': 'bi-check-circle',
                    'bg_class': 'bg-success',
                    'strong': 'Success!'
                },
                'error': {
                    'icon': 'bi-exclamation-triangle',
                    'bg_class': 'bg-danger',
                    'strong': 'Error!'
                },
                'warning': {
                    'icon': 'bi-exclamation-triangle',
                    'bg_class': 'bg-warning',
                    'strong': 'Warning!'
                },
                'info': {
                    'icon': 'bi-info-circle',
                    'bg_class': 'bg-info',
                    'strong': 'Info:'
                }
            }
        }


# Convenience functions for backward compatibility
def add_success_message(request, message: str) -> None:
    """Backward compatibility function for success messages."""
    MessageService.success(request, message)

def add_error_message(request, message: str) -> None:
    """Backward compatibility function for error messages."""
    MessageService.error(request, message)

def add_warning_message(request, message: str) -> None:
    """Backward compatibility function for warning messages."""
    MessageService.warning(request, message)

def add_info_message(request, message: str) -> None:
    """Backward compatibility function for info messages."""
    MessageService.info(request, message)

def create_json_response(success: bool, message: str = '', error: str = '', 
                        data: Optional[Dict] = None) -> JsonResponse:
    """Backward compatibility function for JSON responses."""
    return MessageService.create_json_response(success, message, error, data)
