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

import secrets
import logging
from django.utils.deprecation import MiddlewareMixin
# In Django 5.0, force_str was moved from django.utils.encoding to django.utils.text
try:
    from django.utils.text import force_str
except ImportError:
    from django.utils.encoding import force_str

logger = logging.getLogger('project.security')

class CSPMiddleware(MiddlewareMixin):
    def process_template_response(self, request, response):
        # Ensure csp_nonce is present on the request
        if not hasattr(request, 'csp_nonce'):
            request.csp_nonce = secrets.token_urlsafe(16)
        # Add csp_nonce to the template context if possible
        if hasattr(response, 'context_data') and response.context_data is not None:
            response.context_data['csp_nonce'] = request.csp_nonce
        return response

    """
    Middleware to set a Content Security Policy (CSP) header with a per-request nonce.
    The nonce is made available as 'csp_nonce' in the request and template context.
    """
    def _make_nonce(self):
        # 16 bytes = 128 bits of entropy, url-safe
        return secrets.token_urlsafe(16)

    def process_request(self, request):
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce

    def process_response(self, request, response):
        # Set the CSP header with the nonce
        nonce = getattr(request, 'csp_nonce', None)
        if nonce:
            nonce = force_str(nonce)
            
            # Base CSP directives
            csp_directives = {
                'default-src': ["'self'"],
                'script-src': ["'self'", f"'nonce-{nonce}'"],
                'style-src': ["'self'", f"'nonce-{nonce}'"],
                'img-src': ["'self'", "data:"],
                'font-src': ["'self'", "data:"],
                'connect-src': ["'self'"],
                'object-src': ["'none'"],
                'base-uri': ["'self'"],
                'form-action': ["'self'"],
                'frame-ancestors': ["'none'"],
                'worker-src': ["'none'"],
                # Explicitly block XML transformations
                'media-src': ["'self'"],
            }
            
            # TinyMCE CSP Configuration: Following Claude's superior approach
            # Using django-tinymce package with minimal CSP relaxation
            # Only 'unsafe-inline' for styles (not scripts), no 'unsafe-eval' required
            if '/enquiries/' in request.path and ('create' in request.path or 'edit' in request.path):
                # TinyMCE requires 'unsafe-inline' for styles
                # IMPORTANT: Remove nonce from style-src because 'unsafe-inline' is ignored when nonce is present
                csp_directives['style-src'] = ["'self'", "'unsafe-inline'", "cdn.tiny.cloud"]
                # Add TinyMCE CDN support (django-tinymce uses CDN by default)
                csp_directives['script-src'].append("cdn.tiny.cloud")
                csp_directives['img-src'].extend(["data:", "blob:", "cdn.tiny.cloud"])
                csp_directives['connect-src'].append("api.tiny.cloud")
                logger.info(f"CSP: Added TinyMCE directives for {request.path} (removed nonce from style-src)")

            # This approach is superior because:
            # - Uses mature django-tinymce package
            # - Only requires 'unsafe-inline' for styles, not scripts
            # - No 'unsafe-eval' requirement
            # - Direct HTML compatibility with existing Summernote content
            
            # Build the CSP header string
            csp_parts = []
            for directive, sources in csp_directives.items():
                csp_parts.append(f"{directive} {' '.join(sources)}")
            
            # Add upgrade-insecure-requests as a standalone directive
            csp_parts.append("upgrade-insecure-requests")
            
            # Join all directives with semicolons
            csp = "; ".join(csp_parts)
            
            # Set the CSP header
            response['Content-Security-Policy'] = csp
            
            # Add X-Content-Type-Options header to prevent MIME sniffing
            response['X-Content-Type-Options'] = 'nosniff'
            
        return response
