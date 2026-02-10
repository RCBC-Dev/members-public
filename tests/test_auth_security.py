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
Tests for the Microsoft authentication security middleware.
"""
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from project.middleware.auth_security import MicrosoftAuthSanitizationMiddleware

class MicrosoftAuthSecurityTest(TestCase):
    """Test cases for the MicrosoftAuthSanitizationMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        
        # Mock get_response function that returns a simple HttpResponse
        def get_response(request):
            return HttpResponse("OK")
        
        self.middleware = MicrosoftAuthSanitizationMiddleware(get_response)

    def test_normal_request_passes(self):
        """Test that normal requests pass through the middleware."""
        request = self.factory.get('/accounts/microsoft/login/')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")

    def test_normal_request_with_params_passes(self):
        """Test that normal requests with parameters pass through."""
        request = self.factory.get('/accounts/microsoft/login/', {'code': '12345', 'state': 'abcdef'})
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")

    def test_xsl_injection_in_get_params_blocked(self):
        """Test that XSL injection attempts in GET parameters are blocked."""
        # Test various XSL injection patterns
        suspicious_params = [
            {'code': '<?xml version="1.0"?>'},
            {'code': '<xsl:stylesheet version="1.0">'},
            {'state': '<!DOCTYPE foo SYSTEM "evil.dtd">'},
            {'state': 'data:text/xml,<xml>'},
            {'redirect_uri': '<![CDATA[<]]>script<![CDATA[>]]>alert(1)<![CDATA[<]]>/script<![CDATA[>]]>'},
        ]
        
        for params in suspicious_params:
            request = self.factory.get('/accounts/microsoft/login/', params)
            response = self.middleware(request)
            self.assertEqual(response.status_code, 400, f"Failed to block: {params}")

    def test_xsl_injection_in_post_params_blocked(self):
        """Test that XSL injection attempts in POST parameters are blocked."""
        suspicious_params = [
            {'code': '<?xml version="1.0"?>'},
            {'code': '<xsl:stylesheet version="1.0">'},
        ]
        
        for params in suspicious_params:
            request = self.factory.post('/accounts/microsoft/login/', params)
            response = self.middleware(request)
            self.assertEqual(response.status_code, 400, f"Failed to block: {params}")

    def test_non_microsoft_endpoints_not_affected(self):
        """Test that non-Microsoft endpoints are not affected by the middleware."""
        # Create a request with suspicious content to a non-Microsoft endpoint
        request = self.factory.get('/other/endpoint/', {'param': '<?xml version="1.0"?>'})
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")
