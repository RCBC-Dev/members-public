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
Tests for the custom authentication adapters.
"""
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from allauth.core.exceptions import ImmediateHttpResponse
from project.auth.adapters import SecureMicrosoftAdapter

class SecureMicrosoftAdapterTest(TestCase):
    """Test cases for the SecureMicrosoftAdapter."""

    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = SecureMicrosoftAdapter()

    def test_pre_social_login_normal_request(self):
        """Test that normal requests pass through the adapter."""
        request = self.factory.get('/accounts/microsoft/login/callback/', {'code': '12345', 'state': 'abcdef'})
        request.session = {'socialaccount_state': 'abcdef'}
        
        # Mock sociallogin object
        class MockSocialLogin:
            pass
        
        sociallogin = MockSocialLogin()
        
        # This should not raise an exception
        try:
            self.adapter.pre_social_login(request, sociallogin)
        except ImmediateHttpResponse:
            self.fail("pre_social_login raised ImmediateHttpResponse unexpectedly")

    def test_pre_social_login_invalid_state(self):
        """Test that requests with invalid state are blocked."""
        request = self.factory.get('/accounts/microsoft/login/callback/', {'code': '12345', 'state': 'invalid'})
        request.session = {'socialaccount_state': 'abcdef'}
        
        # Mock sociallogin object
        class MockSocialLogin:
            pass
        
        sociallogin = MockSocialLogin()
        
        # This should raise an ImmediateHttpResponse
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

    def test_pre_social_login_xsl_injection(self):
        """Test that XSL injection attempts are blocked."""
        suspicious_params = [
            {'code': '<?xml version="1.0"?>', 'state': 'abcdef'},
            {'code': '<xsl:stylesheet version="1.0">', 'state': 'abcdef'},
            {'code': '12345', 'state': '<!DOCTYPE foo SYSTEM "evil.dtd">'},
            {'code': '12345', 'state': 'abcdef', 'extra': 'data:text/xml,<xml>'},
        ]
        
        for params in suspicious_params:
            request = self.factory.get('/accounts/microsoft/login/callback/', params)
            request.session = {'socialaccount_state': 'abcdef'}
            
            # Mock sociallogin object
            class MockSocialLogin:
                pass
            
            sociallogin = MockSocialLogin()
            
            # This should raise an ImmediateHttpResponse
            with self.assertRaises(ImmediateHttpResponse):
                self.adapter.pre_social_login(request, sociallogin)
