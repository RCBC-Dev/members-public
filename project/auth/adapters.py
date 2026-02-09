"""
Custom authentication adapters for django-allauth.
Provides additional security checks for authentication flows.
"""
import logging
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.http import HttpResponseBadRequest

from project.security.utils import RequestSecurityUtils, SecurityValidator, SecurityLogger

logger = logging.getLogger('project.security')


class SecureMicrosoftAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for Microsoft authentication that adds additional security checks.
    Specifically targets potential XSL transformation injection vulnerabilities.
    
    Now uses shared security utilities for consistent pattern detection.
    """
    
    def pre_social_login(self, request, sociallogin):
        """
        Perform security checks before processing a social login.
        """
        # Validate the state parameter to prevent CSRF
        state = request.session.get('socialaccount_state')
        request_state = request.GET.get('state')
        
        if state and request_state != state:
            # Log potential CSRF attack attempt
            SecurityLogger.log_security_event(
                event_type='CSRF_ATTEMPT',
                details=f"State parameter mismatch in Microsoft auth flow",
                request_info={
                    'path': request.path,
                    'expected_state': state[:10] + '...' if state else None,
                    'received_state': request_state[:10] + '...' if request_state else None,
                    'user_ip': RequestSecurityUtils.get_client_ip(request)
                },
                severity='WARNING'
            )
            raise ImmediateHttpResponse(HttpResponseBadRequest("Invalid state parameter"))
        
        # Use shared security validation for XSL injection patterns
        error_message = RequestSecurityUtils.validate_request_parameters(
            request, 
            pattern_categories=['xsl_injection'],
            check_get=True,
            check_post=False  # Social auth typically uses GET
        )
        
        if error_message:
            raise ImmediateHttpResponse(HttpResponseBadRequest("Invalid request parameters"))
        
        return super().pre_social_login(request, sociallogin)
