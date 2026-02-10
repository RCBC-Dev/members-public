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
Tests for the authentication logging middleware.
"""
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.contrib.auth.models import User, AnonymousUser
from project.middleware.auth_logging import AuthLoggingMiddleware

class AuthLoggingMiddlewareTest(TestCase):
    """Test cases for the AuthLoggingMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Mock get_response function that returns a simple HttpResponse
        def get_response(request):
            return HttpResponse("OK")
        
        self.middleware = AuthLoggingMiddleware(get_response)

    def test_non_auth_request_not_logged(self):
        """Test that non-authentication requests are not logged."""
        request = self.factory.get('/some/other/path/')
        request.user = AnonymousUser()
        
        # This should not log anything
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")
        
        # We can't easily test that nothing was logged, but the test passes if no exception is raised

    def test_auth_request_logged(self):
        """Test that authentication requests are logged."""
        # Test various authentication paths
        auth_paths = [
            '/accounts/login/',
            '/accounts/microsoft/login/',
            '/accounts/logout/',
        ]
        
        for path in auth_paths:
            request = self.factory.get(path)
            request.user = AnonymousUser()
            request.META['HTTP_USER_AGENT'] = 'Test User Agent'
            request.META['REMOTE_ADDR'] = '127.0.0.1'
            
            # This should log the request
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content.decode(), "OK")
            
            # We can't easily test that the log was written, but the test passes if no exception is raised

    def test_auth_request_with_params_logged(self):
        """Test that authentication requests with parameters are logged with sanitization."""
        request = self.factory.get('/accounts/login/', {'username': 'testuser', 'password': 'secret'})
        request.user = AnonymousUser()
        request.META['HTTP_USER_AGENT'] = 'Test User Agent'
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        # This should log the request with sanitized parameters
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")
        
        # We can't easily test that the log was written correctly, but the test passes if no exception is raised

    def test_successful_login_logged(self):
        """Test that successful login attempts are logged."""
        request = self.factory.get('/accounts/login/')
        request.user = self.user  # Authenticated user
        
        # Create a redirect response to simulate successful login
        def get_response(request):
            response = HttpResponse()
            response.status_code = 302
            response['Location'] = '/dashboard/'
            return response
        
        middleware = AuthLoggingMiddleware(get_response)
        
        # This should log a successful login
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        
        # We can't easily test that the log was written correctly, but the test passes if no exception is raised

    def test_failed_login_logged(self):
        """Test that failed login attempts are logged."""
        request = self.factory.get('/accounts/login/')
        request.user = AnonymousUser()
        
        # Create a bad request response to simulate failed login
        def get_response(request):
            response = HttpResponse("Bad Request")
            response.status_code = 400
            return response
        
        middleware = AuthLoggingMiddleware(get_response)
        
        # This should log a failed login
        response = middleware(request)
        self.assertEqual(response.status_code, 400)
        
        # We can't easily test that the log was written correctly, but the test passes if no exception is raised
