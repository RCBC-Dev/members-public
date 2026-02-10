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
Simple view tests that focus on view function logic without URL routing.
"""

import pytest
import uuid
from datetime import date, timedelta
from unittest.mock import Mock, patch
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.utils import timezone

from application.models import (
    Admin, Ward, Member, Department, Section, Enquiry
)
from application.views import (
    welcome, index
)
from application.services import EnquiryFilterService
from application.date_range_service import DateRangeService


@pytest.mark.django_db
class TestViewFunctions:
    """Test view functions directly without URL routing."""
    
    def setup_method(self):
        """Set up test data."""
        self.factory = RequestFactory()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test data
        self.ward = Ward.objects.create(name='Test Ward')
        self.member_user = User.objects.create_user(username='memberuser')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=self.ward
        )
    
    def test_welcome_view_function(self):
        """Test welcome view function logic."""
        request = self.factory.get('/')
        request.user = Mock()
        request.user.is_authenticated = False
        
        response = welcome(request)
        
        assert response.status_code == 200
    
    def test_welcome_view_redirects_authenticated(self):
        """Test welcome view redirects authenticated users."""
        request = self.factory.get('/')
        request.user = self.user
        
        with patch('application.views.redirect') as mock_redirect:
            welcome(request)
            mock_redirect.assert_called_once()
    
    def test_index_view_function(self):
        """Test index view function logic."""
        # Create some test enquiries
        enquiry1 = Enquiry.objects.create(
            title='Test Enquiry 1',
            description='Description 1',
            member=self.member,
            status='new'
        )
        enquiry2 = Enquiry.objects.create(
            title='Test Enquiry 2',
            description='Description 2',
            member=self.member,
            status='open'
        )
        
        request = self.factory.get('/')
        request.user = self.user
        
        response = index(request)
        
        assert response.status_code == 200
        # For view function tests, we'll just check that it returns successfully
        # Context checking would require rendering the template


class TestHelperFunctions:
    """Test helper functions used by views."""
    
    def test_dates_match_predefined_range_3months(self):
        """Test _dates_match_predefined_range for 3 months using centralized calculation."""
        from application.date_utils import get_preset_date_range

        # Get the actual dates that the system calculates for 3 months
        date_range_info = get_preset_date_range('3months', timezone_aware=False)
        expected_from = date_range_info.date_from_str
        expected_to = date_range_info.date_to_str

        result = DateRangeService.dates_match_predefined_range(
            expected_from,
            expected_to
        )

        assert result is True

    def test_dates_match_predefined_range_6months(self):
        """Test _dates_match_predefined_range for 6 months using centralized calculation."""
        from application.date_utils import get_preset_date_range

        # Get the actual dates that the system calculates for 6 months
        date_range_info = get_preset_date_range('6months', timezone_aware=False)
        expected_from = date_range_info.date_from_str
        expected_to = date_range_info.date_to_str

        result = DateRangeService.dates_match_predefined_range(
            expected_from,
            expected_to
        )

        assert result is True

    def test_dates_match_predefined_range_custom(self):
        """Test _dates_match_predefined_range with custom dates."""
        result = DateRangeService.dates_match_predefined_range(
            '2024-01-01',
            '2024-06-30'
        )

        assert result is False

    def test_dates_match_predefined_range_empty(self):
        """Test _dates_match_predefined_range with empty dates."""
        assert DateRangeService.dates_match_predefined_range('', '') is False
        assert DateRangeService.dates_match_predefined_range(None, None) is False

    def test_dates_match_predefined_range_invalid(self):
        """Test _dates_match_predefined_range with invalid dates."""
        result = DateRangeService.dates_match_predefined_range(
            'invalid-date',
            '2024-01-01'
        )

        assert result is False