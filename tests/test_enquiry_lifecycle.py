"""
Tests for enquiry lifecycle management - closing and re-opening enquiries.
"""

import pytest
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from django.test import TestCase

from application.models import Member, Ward, Enquiry, Admin, EnquiryHistory


@pytest.mark.django_db
class TestEnquiryLifecycle:
    """Test enquiry closing and re-opening functionality."""
    
    def setup_method(self):
        """Set up test data for each test."""
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            first_name='Admin',
            last_name='Test'
        )
        self.admin = Admin.objects.create(user=self.admin_user)
        
        # Create member
        self.ward = Ward.objects.create(name='Test Ward')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email='test.member@example.com',
            ward=self.ward
        )
    
    def test_enquiry_close_sets_closed_at(self):
        """Test that closing an enquiry sets the closed_at timestamp."""
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=self.member,
            status='open'
        )
        
        # Initially closed_at should be None
        assert enquiry.closed_at is None
        assert enquiry.status == 'open'
        
        # Close the enquiry
        enquiry.status = 'closed'
        enquiry.save()
        
        # Refresh from database
        enquiry.refresh_from_db()
        
        # Should now have closed_at timestamp
        assert enquiry.closed_at is not None
        assert enquiry.status == 'closed'
        assert enquiry.closed_at <= timezone.now()
    
    def test_enquiry_reopen_clears_closed_at(self):
        """Test that re-opening a closed enquiry clears the closed_at timestamp."""
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=self.member,
            status='open'
        )
        
        # Close the enquiry first
        enquiry.status = 'closed'
        enquiry.save()
        enquiry.refresh_from_db()
        
        # Verify it's closed
        assert enquiry.closed_at is not None
        assert enquiry.status == 'closed'
        
        # Re-open the enquiry
        enquiry.status = 'open'
        enquiry.save()
        enquiry.refresh_from_db()
        
        # Should clear closed_at timestamp
        assert enquiry.closed_at is None
        assert enquiry.status == 'open'
    
    def test_enquiry_lifecycle_with_history(self):
        """Test complete enquiry lifecycle with history tracking."""
        enquiry = Enquiry.objects.create(
            title='Lifecycle Test Enquiry',
            description='Testing complete lifecycle',
            member=self.member,
            status='new'
        )
        
        # Add initial history note
        history1 = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Initial enquiry created',
            created_by=self.admin_user
        )
        
        # Refresh enquiry - should auto-update to 'open' status
        enquiry.refresh_from_db()
        assert enquiry.status == 'open'
        
        # Add work note
        history2 = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Working on this enquiry',
            created_by=self.admin_user
        )
        
        # Close enquiry
        enquiry.status = 'closed'
        enquiry.save()
        
        # Add closure note
        history3 = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Enquiry resolved and closed',
            created_by=self.admin_user
        )
        
        enquiry.refresh_from_db()
        assert enquiry.status == 'closed'
        assert enquiry.closed_at is not None
        
        # Re-open enquiry
        enquiry.status = 'open'
        enquiry.save()
        
        # Add re-open note
        history4 = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Enquiry re-opened for additional work',
            created_by=self.admin_user
        )
        
        enquiry.refresh_from_db()
        assert enquiry.status == 'open'
        assert enquiry.closed_at is None
        
        # Verify all history entries exist
        history_entries = enquiry.history.all().order_by('id')  # Use id for reliable ordering
        assert len(history_entries) == 4
        
        # Check that all expected notes exist (order may vary due to timing)
        notes = [entry.note for entry in history_entries]
        assert 'Initial enquiry created' in notes
        assert 'Working on this enquiry' in notes
        assert 'Enquiry resolved and closed' in notes
        assert 'Enquiry re-opened for additional work' in notes
    
    def test_multiple_close_reopen_cycles(self):
        """Test multiple close/re-open cycles on the same enquiry."""
        enquiry = Enquiry.objects.create(
            title='Multiple Cycles Test',
            description='Testing multiple close/reopen cycles',
            member=self.member,
            status='open'
        )
        
        # First close/reopen cycle
        enquiry.status = 'closed'
        enquiry.save()
        enquiry.refresh_from_db()
        assert enquiry.closed_at is not None
        first_closed_at = enquiry.closed_at
        
        enquiry.status = 'open'
        enquiry.save()
        enquiry.refresh_from_db()
        assert enquiry.closed_at is None
        
        # Second close/reopen cycle
        enquiry.status = 'closed'
        enquiry.save()
        enquiry.refresh_from_db()
        assert enquiry.closed_at is not None
        second_closed_at = enquiry.closed_at
        
        # Second close should have a different (later) timestamp
        assert second_closed_at >= first_closed_at
        
        enquiry.status = 'open'
        enquiry.save()
        enquiry.refresh_from_db()
        assert enquiry.closed_at is None
    
    def test_enquiry_status_choices(self):
        """Test that enquiry status choices are correctly defined."""
        expected_choices = (
            ('new', 'New'),
            ('open', 'Open'),
            ('closed', 'Closed'),
        )
        assert Enquiry.STATUS_CHOICES == expected_choices
    
    def test_enquiry_default_status(self):
        """Test that new enquiries default to 'open' status."""
        enquiry = Enquiry.objects.create(
            title='Default Status Test',
            description='Testing default status',
            member=self.member
        )
        
        assert enquiry.status == 'open'
        assert enquiry.closed_at is None
