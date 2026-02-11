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
Tests for the new attachment upload functionality on enquiry detail page.
"""
import json
import os
import tempfile
import shutil
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from application.models import Enquiry, EnquiryAttachment, EnquiryHistory, Member, Ward


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AttachmentUploadTestCase(TestCase):
    """Test cases for the new attachment upload functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.test_files_created = []  # Track files created during tests
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test ward and member
        self.ward = Ward.objects.create(name='Test Ward')
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email='test.member@example.com',
            ward=self.ward
        )
        
        # Create test enquiry (open)
        self.open_enquiry = Enquiry.objects.create(
            title='Test Open Enquiry',
            description='Test Description',
            member=self.member,
            reference='MEM-24-0001',
            status='open'
        )
        
        # Create test enquiry (closed)
        self.closed_enquiry = Enquiry.objects.create(
            title='Test Closed Enquiry',
            description='Test Description',
            member=self.member,
            reference='MEM-24-0002',
            status='closed'
        )
        
        # Login the user
        self.client.login(username='testuser', password='testpass123')

    def tearDown(self):
        """Clean up test data and files."""
        # Clean up the temporary media directory
        if hasattr(settings, 'MEDIA_ROOT') and os.path.exists(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def create_test_image_file(self, filename='test.jpg'):
        """Create a test image file with minimal valid JPEG content."""
        # Minimal valid JPEG file content (1x1 pixel)
        jpeg_content = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342'
            b'\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01'
            b'\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xaa\xff\xd9'
        )
        return SimpleUploadedFile(
            filename,
            jpeg_content,
            content_type='image/jpeg'
        )

    def create_test_pdf_file(self, filename='test.pdf'):
        """Create a test PDF file with minimal valid PDF content."""
        # Minimal valid PDF content (empty document)
        pdf_content = (
            b'%PDF-1.4\n'
            b'1 0 obj\n'
            b'<<\n'
            b'/Type /Catalog\n'
            b'/Pages 2 0 R\n'
            b'>>\n'
            b'endobj\n'
            b'2 0 obj\n'
            b'<<\n'
            b'/Type /Pages\n'
            b'/Kids [3 0 R]\n'
            b'/Count 1\n'
            b'>>\n'
            b'endobj\n'
            b'3 0 obj\n'
            b'<<\n'
            b'/Type /Page\n'
            b'/Parent 2 0 R\n'
            b'/MediaBox [0 0 612 792]\n'
            b'>>\n'
            b'endobj\n'
            b'xref\n'
            b'0 4\n'
            b'0000000000 65535 f \n'
            b'0000000009 00000 n \n'
            b'0000000074 00000 n \n'
            b'0000000120 00000 n \n'
            b'trailer\n'
            b'<<\n'
            b'/Size 4\n'
            b'/Root 1 0 R\n'
            b'>>\n'
            b'startxref\n'
            b'207\n'
            b'%%EOF\n'
        )
        return SimpleUploadedFile(
            filename,
            pdf_content,
            content_type='application/pdf'
        )

    def test_attach_file_to_open_enquiry(self):
        """Test attaching a file to an open enquiry."""
        url = reverse('application:api_upload_photos')
        test_file = self.create_test_image_file('test_image.jpg')

        response = self.client.post(url, {'file': test_file, 'enquiry_id': self.open_enquiry.id})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)

        # Check that attachment was created
        attachment = EnquiryAttachment.objects.filter(enquiry=self.open_enquiry).first()
        self.assertIsNotNone(attachment)
        self.assertEqual(attachment.filename, 'test_image.jpg')
        self.assertEqual(attachment.uploaded_by, self.user)

        # Check that history entry was created
        history = EnquiryHistory.objects.filter(enquiry=self.open_enquiry).first()
        self.assertIsNotNone(history)
        self.assertIn('1 file(s) manually attached', history.note)
        self.assertIn('test_image.jpg', history.note)

    def test_attach_file_to_closed_enquiry(self):
        """Test attaching a file to a closed enquiry."""
        url = reverse('application:api_upload_photos')
        test_file = self.create_test_pdf_file('test_document.pdf')

        response = self.client.post(url, {'file': test_file, 'enquiry_id': self.closed_enquiry.id})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)

        # Check that attachment was created
        attachment = EnquiryAttachment.objects.filter(enquiry=self.closed_enquiry).first()
        self.assertIsNotNone(attachment)
        self.assertEqual(attachment.filename, 'test_document.pdf')
        self.assertEqual(attachment.uploaded_by, self.user)

        # Check that history entry was created with consistent format
        history = EnquiryHistory.objects.filter(enquiry=self.closed_enquiry).first()
        self.assertIsNotNone(history)
        self.assertIn('1 file(s) manually attached', history.note)
        self.assertIn('test_document.pdf', history.note)

    def test_attach_unsupported_file_type(self):
        """Test attaching an unsupported file type."""
        url = reverse('application:api_upload_photos')
        test_file = SimpleUploadedFile(
            'test.txt',
            b'text file content',
            content_type='text/plain'
        )

        response = self.client.post(url, {'file': test_file, 'enquiry_id': self.open_enquiry.id})

        self.assertEqual(response.status_code, 200)  # api_upload_photos returns 200 with success: false
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('File type not supported', data['error'])

    def test_attach_file_no_file_provided(self):
        """Test API endpoint when no file is provided."""
        url = reverse('application:api_upload_photos')

        response = self.client.post(url, {'enquiry_id': self.open_enquiry.id})

        self.assertEqual(response.status_code, 200)  # api_upload_photos returns 200 with success: false
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('No file provided', data['error'])

    def test_attach_file_nonexistent_enquiry(self):
        """Test attaching a file to a non-existent enquiry."""
        url = reverse('application:api_upload_photos')
        test_file = self.create_test_image_file('test.jpg')

        response = self.client.post(url, {'file': test_file, 'enquiry_id': 99999})

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Enquiry with ID 99999 does not exist', data['error'])

    def test_attach_file_wrong_method(self):
        """Test API endpoint rejects wrong HTTP method."""
        url = reverse('application:api_upload_photos')

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

    def test_enquiry_detail_page_contains_dropzone(self):
        """Test that the enquiry detail page contains the attachment dropzone."""
        url = reverse('application:enquiry_detail', args=[self.open_enquiry.id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'attachment-dropzone')
        self.assertContains(response, 'Drop files here or click to browse')
        # Check for the actual URL that would be generated
        expected_url = reverse('application:api_upload_photos')
        self.assertContains(response, expected_url)

    def test_enquiry_detail_page_closed_enquiry_has_dropzone(self):
        """Test that closed enquiries also have the attachment dropzone."""
        url = reverse('application:enquiry_detail', args=[self.closed_enquiry.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'attachment-dropzone')
        self.assertContains(response, 'Drop files here or click to browse')

    def test_attachment_count_display(self):
        """Test that the attachment count is displayed correctly."""
        # Create some attachments
        EnquiryAttachment.objects.create(
            enquiry=self.open_enquiry,
            filename='test1.jpg',
            file_path='test/path1.jpg',
            file_size=1024,
            uploaded_by=self.user
        )
        EnquiryAttachment.objects.create(
            enquiry=self.open_enquiry,
            filename='test2.pdf',
            file_path='test/path2.pdf',
            file_size=2048,
            uploaded_by=self.user
        )
        
        url = reverse('application:enquiry_detail', args=[self.open_enquiry.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check for the attachment count in the span element
        self.assertContains(response, '<span id="attachment-count">2</span>')
        self.assertContains(response, 'Attachments (')
