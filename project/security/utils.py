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
Shared security utilities for the Members Enquiries System.

This module provides reusable security functions used across middleware,
adapters, and other security components to prevent code duplication and
ensure consistent security patterns.
"""

import re
import logging
from typing import List, Dict, Optional, Union

logger = logging.getLogger('project.security')


class SecurityPatterns:
    """
    Centralized security pattern definitions and detection logic.
    """
    
    # XSL injection patterns - comprehensive list of suspicious content
    XSL_INJECTION_PATTERNS = [
        r'<\?xml',              # XML declaration
        r'<xsl:',               # XSL tag
        r'<!DOCTYPE',           # DOCTYPE declaration
        r'SYSTEM\s+["\']',      # SYSTEM keyword (used in DTD)
        r'PUBLIC\s+["\']',      # PUBLIC keyword (used in DTD)
        r'<!ENTITY',            # XML entity declaration
        r'data:text/xml',       # Data URL with XML content
        r'xmlns:xsl=',          # XSL namespace declaration
        r'<!\[CDATA\[',         # CDATA section start
        r'\]\]>',               # CDATA section end
        r'<script',             # Script tags that might be part of an XSS attack
        r'</script',            # Closing script tag
        r'javascript:',         # JavaScript URLs
        r'vbscript:',           # VBScript URLs
        r'file://',             # File protocol (potential LFI)
        r'ftp://',              # FTP protocol
        r'<iframe',             # Iframe tags
        r'<object',             # Object tags
        r'<embed',              # Embed tags
        r'<form',               # Form tags (potential CSRF)
        r'onload\s*=',          # Event handlers
        r'onerror\s*=',         # Error event handlers
        r'onclick\s*=',         # Click event handlers
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'union\s+select',      # UNION SELECT
        r'drop\s+table',        # DROP TABLE
        r'insert\s+into',       # INSERT INTO
        r'delete\s+from',       # DELETE FROM
        r'update\s+.*set',      # UPDATE ... SET
        r'exec\s*\(',           # EXEC function calls
        r'sp_\w+',              # Stored procedures
        r'xp_\w+',              # Extended stored procedures
        r'--\s*$',              # SQL comments
        r'/\*.*\*/',            # SQL block comments
        r"'\s*or\s+'",          # OR conditions with quotes
        r"'\s*and\s+'",         # AND conditions with quotes
        r'0x[0-9a-f]+',         # Hexadecimal values
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\./+',              # Directory traversal
        r'\.\.\\+',             # Windows directory traversal
        r'%2e%2e%2f',           # URL encoded ../
        r'%2e%2e%5c',           # URL encoded ..\
        r'\.\.%2f',             # Mixed encoding
        r'\.\.%5c',             # Mixed encoding
        r'/etc/passwd',         # Common target file
        r'/proc/self/environ',  # Process environment
        r'\\windows\\system32', # Windows system directory
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r';\s*\w+',             # Command chaining with semicolon
        r'\|\s*\w+',            # Command piping
        r'&&\s*\w+',            # Command chaining with AND
        r'\|\|\s*\w+',          # Command chaining with OR
        r'`.*`',                # Backtick command execution
        r'\$\(.*\)',            # Command substitution
        r'nc\s+-',              # Netcat commands
        r'wget\s+',             # Wget commands
        r'curl\s+',             # Curl commands
        r'bash\s+',             # Bash execution
        r'sh\s+',               # Shell execution
        r'python\s+',           # Python execution
        r'perl\s+',             # Perl execution
        r'php\s+',              # PHP execution
    ]
    
    @classmethod
    def get_all_patterns(cls) -> Dict[str, List[str]]:
        """Get all security patterns organized by category."""
        return {
            'xsl_injection': cls.XSL_INJECTION_PATTERNS,
            'sql_injection': cls.SQL_INJECTION_PATTERNS,
            'path_traversal': cls.PATH_TRAVERSAL_PATTERNS,
            'command_injection': cls.COMMAND_INJECTION_PATTERNS,
        }


class SecurityValidator:
    """
    Security validation utilities for detecting various attack patterns.
    """
    
    @staticmethod
    def contains_xsl_injection_pattern(value: str) -> bool:
        """
        Check if the value contains patterns related to XSL injection attacks.
        
        Args:
            value: String value to check
            
        Returns:
            True if suspicious patterns are found, False otherwise
        """
        if not isinstance(value, str):
            return False
        
        return SecurityValidator._check_patterns(value, SecurityPatterns.XSL_INJECTION_PATTERNS)
    
    @staticmethod
    def contains_sql_injection_pattern(value: str) -> bool:
        """
        Check if the value contains patterns related to SQL injection attacks.
        
        Args:
            value: String value to check
            
        Returns:
            True if suspicious patterns are found, False otherwise
        """
        if not isinstance(value, str):
            return False
        
        return SecurityValidator._check_patterns(value, SecurityPatterns.SQL_INJECTION_PATTERNS)
    
    @staticmethod
    def contains_path_traversal_pattern(value: str) -> bool:
        """
        Check if the value contains path traversal patterns.
        
        Args:
            value: String value to check
            
        Returns:
            True if suspicious patterns are found, False otherwise
        """
        if not isinstance(value, str):
            return False
        
        return SecurityValidator._check_patterns(value, SecurityPatterns.PATH_TRAVERSAL_PATTERNS)
    
    @staticmethod
    def contains_command_injection_pattern(value: str) -> bool:
        """
        Check if the value contains command injection patterns.
        
        Args:
            value: String value to check
            
        Returns:
            True if suspicious patterns are found, False otherwise
        """
        if not isinstance(value, str):
            return False
        
        return SecurityValidator._check_patterns(value, SecurityPatterns.COMMAND_INJECTION_PATTERNS)
    
    @staticmethod
    def contains_any_suspicious_pattern(value: str, 
                                      pattern_categories: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Check if the value contains any suspicious patterns across multiple categories.
        
        Args:
            value: String value to check
            pattern_categories: List of categories to check. If None, checks all categories.
            
        Returns:
            Dictionary with category names as keys and boolean results as values
        """
        if not isinstance(value, str):
            return {}
        
        if pattern_categories is None:
            pattern_categories = ['xsl_injection', 'sql_injection', 'path_traversal', 'command_injection']
        
        results = {}
        all_patterns = SecurityPatterns.get_all_patterns()
        
        for category in pattern_categories:
            if category in all_patterns:
                results[category] = SecurityValidator._check_patterns(value, all_patterns[category])
            else:
                logger.warning(f"Unknown security pattern category: {category}")
                results[category] = False
        
        return results
    
    @staticmethod
    def _check_patterns(value: str, patterns: List[str]) -> bool:
        """
        Check if the value matches any of the provided regex patterns.
        
        Args:
            value: String value to check
            patterns: List of regex patterns
            
        Returns:
            True if any pattern matches, False otherwise
        """
        try:
            for pattern in patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.debug(f"Security pattern matched: '{pattern}' in value: {value[:100]}...")
                    return True
            return False
        except re.error as e:
            logger.error(f"Regex error in security pattern checking: {e}")
            return False
    
    @staticmethod
    def sanitize_log_value(value: str, max_length: int = 100) -> str:
        """
        Sanitize a value for safe logging by truncating and removing sensitive patterns.
        
        Args:
            value: String value to sanitize
            max_length: Maximum length of the returned string
            
        Returns:
            Sanitized string safe for logging
        """
        if not isinstance(value, str):
            return str(value)[:max_length]
        
        # Remove potential credentials or sensitive data
        sanitized = re.sub(r'(password|token|key|secret)=[^&\s]*', r'\1=***', value, flags=re.IGNORECASE)
        
        # Remove email addresses
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)
        
        # Remove potential IP addresses
        sanitized = re.sub(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '[IP]', sanitized)
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + '...'
        
        return sanitized


class SecurityLogger:
    """
    Centralized security logging utilities.
    """
    
    @staticmethod
    def log_security_event(event_type: str, 
                          details: str, 
                          request_info: Optional[Dict] = None,
                          severity: str = 'WARNING') -> None:
        """
        Log a security event with standardized format.
        
        Args:
            event_type: Type of security event (e.g., 'XSL_INJECTION_ATTEMPT')
            details: Detailed description of the event
            request_info: Optional request information (path, IP, user agent, etc.)
            severity: Log severity level
        """
        # Prepare log message
        log_message = f"SECURITY_EVENT: {event_type} - {details}"
        
        if request_info:
            sanitized_info = {}
            for key, value in request_info.items():
                if isinstance(value, str):
                    sanitized_info[key] = SecurityValidator.sanitize_log_value(value)
                else:
                    sanitized_info[key] = str(value)
            
            log_message += f" - Request info: {sanitized_info}"
        
        # Log with appropriate severity
        log_level = getattr(logging, severity.upper(), logging.WARNING)
        logger.log(log_level, log_message)
    
    @staticmethod
    def log_blocked_request(attack_type: str, 
                           value: str, 
                           request_path: str,
                           user_ip: Optional[str] = None) -> None:
        """
        Log a blocked malicious request.
        
        Args:
            attack_type: Type of attack detected
            value: The malicious value that was detected
            request_path: The request path where attack was detected
            user_ip: Optional user IP address
        """
        request_info = {
            'path': request_path,
            'malicious_value': value,
        }
        
        if user_ip:
            request_info['ip'] = user_ip
        
        SecurityLogger.log_security_event(
            event_type=f"{attack_type.upper()}_BLOCKED",
            details=f"Blocked {attack_type} attempt",
            request_info=request_info,
            severity='WARNING'
        )


class RequestSecurityUtils:
    """
    Utilities for securing Django requests.
    """
    
    @staticmethod
    def validate_request_parameters(request, 
                                  pattern_categories: Optional[List[str]] = None,
                                  check_get: bool = True,
                                  check_post: bool = True) -> Optional[str]:
        """
        Validate all parameters in a Django request for security threats.
        
        Args:
            request: Django request object
            pattern_categories: List of pattern categories to check
            check_get: Whether to check GET parameters
            check_post: Whether to check POST parameters
            
        Returns:
            None if validation passes, error message string if threats detected
        """
        if pattern_categories is None:
            pattern_categories = ['xsl_injection']  # Default to XSL injection for auth middleware
        
        # Check GET parameters
        if check_get:
            for key, value in request.GET.items():
                if isinstance(value, str):
                    threats = SecurityValidator.contains_any_suspicious_pattern(value, pattern_categories)
                    if any(threats.values()):
                        threat_types = [cat for cat, detected in threats.items() if detected]
                        SecurityLogger.log_blocked_request(
                            attack_type=' + '.join(threat_types),
                            value=value,
                            request_path=request.path,
                            user_ip=RequestSecurityUtils.get_client_ip(request)
                        )
                        return f"Invalid request parameters detected in GET parameter '{key}'"
        
        # Check POST parameters
        if check_post and request.method == 'POST':
            for key, value in request.POST.items():
                if isinstance(value, str):
                    threats = SecurityValidator.contains_any_suspicious_pattern(value, pattern_categories)
                    if any(threats.values()):
                        threat_types = [cat for cat, detected in threats.items() if detected]
                        SecurityLogger.log_blocked_request(
                            attack_type=' + '.join(threat_types),
                            value=value,
                            request_path=request.path,
                            user_ip=RequestSecurityUtils.get_client_ip(request)
                        )
                        return f"Invalid request parameters detected in POST parameter '{key}'"
        
        return None
    
    @staticmethod
    def get_client_ip(request) -> Optional[str]:
        """
        Get the client IP address from the request, handling proxies.
        
        Args:
            request: Django request object
            
        Returns:
            Client IP address as string, or None if not found
        """
        # Check X-Forwarded-For header first (proxy/load balancer)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP (client IP before any proxies)
            ip = x_forwarded_for.split(',')[0].strip()
            return ip
        
        # Fallback to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR')
    
    @staticmethod
    def validate_auth_request(request) -> Optional[str]:
        """
        Specifically validate authentication-related requests.
        This is a convenience method for auth middleware.
        
        Args:
            request: Django request object
            
        Returns:
            None if validation passes, error message if threats detected
        """
        # Check the URL path itself
        if SecurityValidator.contains_xsl_injection_pattern(request.path):
            SecurityLogger.log_blocked_request(
                attack_type='XSL_INJECTION',
                value=request.path,
                request_path=request.path,
                user_ip=RequestSecurityUtils.get_client_ip(request)
            )
            return "Invalid request path"
        
        # Check the full URL (path + query string) to catch malicious patterns
        # that might be split across the URL parsing boundary
        query_string = request.META.get('QUERY_STRING', '')
        if query_string:
            full_url = request.path + '?' + query_string
            if SecurityValidator.contains_xsl_injection_pattern(full_url):
                SecurityLogger.log_blocked_request(
                    attack_type='XSL_INJECTION',
                    value=full_url,
                    request_path=request.path,
                    user_ip=RequestSecurityUtils.get_client_ip(request)
                )
                return "Invalid request path"
        
        # Check parameters
        return RequestSecurityUtils.validate_request_parameters(
            request, 
            pattern_categories=['xsl_injection'],
            check_get=True,
            check_post=True
        )