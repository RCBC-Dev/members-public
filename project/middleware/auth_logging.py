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
Middleware for logging authentication attempts.
"""

import logging
import json
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("project.security")


class AuthLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log authentication attempts.
    Logs all requests to authentication endpoints to help detect potential attacks.
    """

    sync_only = True

    def __init__(self, get_response):
        super().__init__(get_response)
        # Authentication-related paths to monitor
        self.auth_paths = [
            "/accounts/login/",
            "/accounts/microsoft/",
            "/accounts/logout/",
        ]

    def process_request(self, request):
        """Log authentication-related requests."""
        # Check if this is an authentication-related request
        if any(request.path.startswith(path) for path in self.auth_paths):
            # Log basic request information
            log_data = {
                "path": request.path,
                "method": request.method,
                "ip": self._get_client_ip(request),
                "user": (
                    str(request.user) if request.user.is_authenticated else "anonymous"
                ),
                "user_agent": request.META.get("HTTP_USER_AGENT", "unknown"),
            }

            # Log parameters (sanitize sensitive data)
            if request.method == "GET" and request.GET:
                log_data["get_params"] = self._sanitize_params(dict(request.GET))

            # Don't log POST data as it might contain sensitive information
            # Just log that there was POST data
            if request.method == "POST" and request.POST:
                log_data["has_post_data"] = True

            logger.info(f"Auth request: {json.dumps(log_data)}")

        return None

    def process_response(self, request, response):
        """Log authentication responses with status codes."""
        if any(request.path.startswith(path) for path in self.auth_paths):
            # Log response status
            log_data = {
                "path": request.path,
                "status_code": response.status_code,
                "user": (
                    str(request.user) if request.user.is_authenticated else "anonymous"
                ),
            }

            # Log successful and failed authentication attempts
            if request.path.startswith("/accounts/login/") or request.path.startswith(
                "/accounts/microsoft/"
            ):
                if (
                    response.status_code == 302 and request.user.is_authenticated
                ):  # Successful login typically redirects
                    logger.info(f"Successful authentication: {json.dumps(log_data)}")
                elif (
                    response.status_code == 400
                ):  # Bad request might indicate attack attempt
                    logger.warning(
                        f"Rejected authentication attempt: {json.dumps(log_data)}"
                    )

        return response

    def _get_client_ip(self, request):
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # X-Forwarded-For can be a comma-separated list of IPs.
            # The client's IP will be the first one.
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "unknown")
        return ip

    def _sanitize_params(self, params_dict):
        """Sanitize request parameters to avoid logging sensitive data."""
        # List of parameter names that might contain sensitive data
        sensitive_params = [
            "password",
            "token",
            "access_token",
            "id_token",
            "refresh_token",
            "secret",
        ]

        sanitized = {}
        for key, value in params_dict.items():
            if any(sensitive in key.lower() for sensitive in sensitive_params):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value

        return sanitized
