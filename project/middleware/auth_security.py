"""
Middleware for enhancing security of authentication flows.
Specifically targets potential XSL transformation injection vulnerabilities.
"""
import logging
from django.http import HttpResponseBadRequest

from project.security.utils import RequestSecurityUtils

logger = logging.getLogger('project.security')


class MicrosoftAuthSanitizationMiddleware:
    """
    Middleware to sanitize input parameters for Microsoft authentication endpoints.
    Prevents XSL transformation injection attacks by sanitizing request parameters.
    
    Now uses shared security utilities for consistent pattern detection.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process requests to Microsoft auth endpoints
        if request.path.startswith('/accounts/microsoft/'):
            logger.debug(f"Processing Microsoft auth request: {request.path}")
            
            # Use shared security utility for validation
            error_message = RequestSecurityUtils.validate_auth_request(request)
            if error_message:
                return HttpResponseBadRequest("Invalid request")
        
        return self.get_response(request)
