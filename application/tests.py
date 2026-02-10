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

import uuid
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import Enquiry, Member, Ward, Department, Section, JobType, EnquiryHistory
from .forms import EnquiryForm, EnquiryHistoryForm
from .utils import create_enquiry_from_email


class EnquiryModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testmember',
            email='test@example.com',
            password='password'
        )
        self.ward = Ward.objects.create(name='Test Ward')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=self.ward
        )
        self.department = Department.objects.create(name='Test Department')
        self.section = Section.objects.create(name='Test Section', department=self.department)
        self.job_type = JobType.objects.create(name='Test Job Type')

    def test_enquiry_creation(self):
        """Test that an enquiry can be created with required fields."""
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test description',
            member=self.member,
            reference='TEST001'
        )
        self.assertEqual(enquiry.title, 'Test Enquiry')
        self.assertEqual(enquiry.status, 'new')  # Default status
        self.assertEqual(enquiry.member, self.member)
        self.assertIsNotNone(enquiry.created_at)

    def test_enquiry_reference_generation(self):
        """Test that enquiry references are generated correctly."""
        reference = Enquiry.generate_reference()
        self.assertTrue(reference.startswith('MEM-'))
        self.assertEqual(len(reference), 11)  # MEM-YY-NNNN format (e.g., MEM-25-0001)

    def test_enquiry_due_date_calculation(self):
        """Test that due dates are calculated correctly (5 working days)."""
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test description',
            member=self.member,
            reference='TEST001'
        )
        # Due date should be approximately 5 days from creation
        expected_due = enquiry.created_at + timedelta(days=5)
        self.assertAlmostEqual(
            enquiry.due_date.date(),
            expected_due.date(),
            delta=timedelta(days=2)  # Allow some flexibility for weekends
        )

    def test_enquiry_str_method(self):
        """Test the string representation of an enquiry."""
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test description',
            member=self.member,
            reference='TEST001'
        )
        expected_str = f"TEST001 - Test Enquiry"
        self.assertEqual(str(enquiry), expected_str)


class EnquiryFormTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testmember',
            email='test@example.com',
            password='password'
        )
        self.ward = Ward.objects.create(name='Test Ward')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=self.ward
        )
        self.department = Department.objects.create(name='Test Department')
        self.section = Section.objects.create(name='Test Section', department=self.department)
        self.job_type = JobType.objects.create(name='Test Job Type')

        self.base_data = {
            'title': 'Test Enquiry',
            'description': 'A test description.',
            'member': self.member.id,
            'section': self.section.id,
            'job_type': self.job_type.id,
        }

    def test_enquiry_form_valid(self):
        """Test that the EnquiryForm is valid with correct data."""
        form = EnquiryForm(data=self.base_data)
        self.assertTrue(form.is_valid(), form.errors.as_text())

    def test_enquiry_form_missing_required_fields(self):
        """Test that the form is invalid if required fields are missing."""
        invalid_data = self.base_data.copy()
        del invalid_data['title']
        form = EnquiryForm(data=invalid_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_enquiry_form_member_required(self):
        """Test that member field is required."""
        invalid_data = self.base_data.copy()
        del invalid_data['member']
        form = EnquiryForm(data=invalid_data)
        self.assertFalse(form.is_valid())
        self.assertIn('member', form.errors)


class EnquiryHistoryFormTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        self.ward = Ward.objects.create(name='Test Ward')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=self.ward
        )
        self.enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test description',
            member=self.member,
            reference='TEST001'
        )

    def test_history_form_valid(self):
        """Test that the EnquiryHistoryForm is valid with correct data."""
        form_data = {'note': 'Test history note'}
        form = EnquiryHistoryForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_text())

    def test_history_form_missing_note(self):
        """Test that the form is invalid without a note."""
        form = EnquiryHistoryForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('note', form.errors)


class EnquiryViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        self.ward = Ward.objects.create(name='Test Ward')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=self.ward
        )
        self.department = Department.objects.create(name='Test Department')
        self.section = Section.objects.create(name='Test Section', department=self.department)
        self.enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test description',
            member=self.member,
            reference='TEST001'
        )

    def test_enquiry_list_view_requires_login(self):
        """Test that enquiry list view requires authentication."""
        response = self.client.get(reverse('application:enquiry_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_enquiry_list_view_authenticated(self):
        """Test that authenticated users can access enquiry list."""
        self.client.login(username='testuser', password='password')
        response = self.client.get(reverse('application:enquiry_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enquiries')

    def test_enquiry_detail_view_requires_login(self):
        """Test that enquiry detail view requires authentication."""
        response = self.client.get(reverse('application:complaint_detail', args=[self.enquiry.pk]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_enquiry_detail_view_authenticated(self):
        """Test that authenticated users can access enquiry detail."""
        self.client.login(username='testuser', password='password')
        response = self.client.get(reverse('application:complaint_detail', args=[self.enquiry.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.enquiry.title)

    def test_enquiry_create_view_requires_login(self):
        """Test that enquiry create view requires authentication."""
        response = self.client.get(reverse('application:complaint_create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login


class EmailParsingTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        self.ward = Ward.objects.create(name='Test Ward')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=self.ward
        )

    def test_create_enquiry_from_email_success(self):
        """Test successful enquiry creation from email data."""
        email_data = {
            'email_from': 'Test User <test@example.com>',
            'subject': 'Test Email Subject',
            'body_content': 'Test email body content',
            'email_date_str': 'Jan 01, 2024 10:00 UTC'
        }

        result = create_enquiry_from_email(email_data, self.user)

        self.assertTrue(result['success'])
        self.assertIsInstance(result['enquiry'], Enquiry)
        self.assertEqual(result['enquiry'].title, 'Test Email Subject')
        self.assertEqual(result['enquiry'].member, self.member)

    def test_create_enquiry_from_email_no_member(self):
        """Test enquiry creation fails when no member found."""
        email_data = {
            'email_from': 'Unknown User <unknown@example.com>',
            'subject': 'Test Email Subject',
            'body_content': 'Test email body content',
            'email_date_str': 'Jan 01, 2024 10:00 UTC'
        }

        result = create_enquiry_from_email(email_data, self.user)

        self.assertFalse(result['success'])
        self.assertIn('No active member found', result['error'])

    def test_create_enquiry_from_email_invalid_email(self):
        """Test enquiry creation fails with invalid email format."""
        email_data = {
            'email_from': '',  # Empty email_from
            'subject': 'Test Email Subject',
            'body_content': 'Test email body content',
            'email_date_str': 'Jan 01, 2024 10:00 UTC'
        }

        result = create_enquiry_from_email(email_data, self.user)

        self.assertFalse(result['success'])
        self.assertIn('Could not extract sender email', result['error'])
