"""
Test cases for enquiry image removal functionality.
"""
import json
import pytest
import uuid
from django.test import TestCase
from django.contrib.auth.models import User
from application.models import Member, Ward, Enquiry, EnquiryAttachment
from application.services import EnquiryService


@pytest.mark.django_db
class TestEnquiryImageRemoval(TestCase):
    """Test enquiry image removal functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        self.ward = Ward.objects.create(name='Test Ward')
        self.member_user = User.objects.create_user(
            username='member',
            email='member@test.com',
            password='testpass123'
        )
        self.member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=self.ward
        )
    
    def test_create_enquiry_with_partial_images(self):
        """Test creating enquiry with some images removed (simulating frontend removal)."""
        form_data = {
            'title': 'Test Enquiry',
            'description': 'Test Description',
            'member': self.member
        }
        
        # Simulate original extracted images
        original_images = [
            {
                'original_filename': 'logo.jpg',
                'file_path': 'attachments/logo.jpg',
                'file_size': 1024
            },
            {
                'original_filename': 'document.png',
                'file_path': 'attachments/document.png',
                'file_size': 2048
            },
            {
                'original_filename': 'signature.gif',
                'file_path': 'attachments/signature.gif',
                'file_size': 512
            }
        ]
        
        # Simulate user removing the first image (logo.jpg) and third image (signature.gif)
        # This would be done by the JavaScript frontend
        filtered_images = [
            {
                'original_filename': 'document.png',
                'file_path': 'attachments/document.png',
                'file_size': 2048
            }
        ]
        
        enquiry = EnquiryService.create_enquiry_with_attachments(
            form_data=form_data,
            user=self.admin_user,
            extracted_images_json=json.dumps(filtered_images)
        )
        
        # Verify enquiry was created
        assert enquiry.title == 'Test Enquiry'
        assert enquiry.member == self.member
        
        # Verify only the selected image was attached
        attachments = EnquiryAttachment.objects.filter(enquiry=enquiry)
        assert attachments.count() == 1
        assert attachments.first().filename == 'document.png'
        assert attachments.first().file_size == 2048
    
    def test_create_enquiry_with_all_images_removed(self):
        """Test creating enquiry with all images removed."""
        form_data = {
            'title': 'Test Enquiry',
            'description': 'Test Description',
            'member': self.member
        }
        
        # Simulate user removing all images (empty array)
        filtered_images = []
        
        enquiry = EnquiryService.create_enquiry_with_attachments(
            form_data=form_data,
            user=self.admin_user,
            extracted_images_json=json.dumps(filtered_images)
        )
        
        # Verify enquiry was created
        assert enquiry.title == 'Test Enquiry'
        assert enquiry.member == self.member
        
        # Verify no attachments were created
        attachments = EnquiryAttachment.objects.filter(enquiry=enquiry)
        assert attachments.count() == 0
    
    def test_create_enquiry_with_no_extracted_images(self):
        """Test creating enquiry with no extracted images (empty string)."""
        form_data = {
            'title': 'Test Enquiry',
            'description': 'Test Description',
            'member': self.member
        }
        
        enquiry = EnquiryService.create_enquiry_with_attachments(
            form_data=form_data,
            user=self.admin_user,
            extracted_images_json=''
        )
        
        # Verify enquiry was created
        assert enquiry.title == 'Test Enquiry'
        assert enquiry.member == self.member
        
        # Verify no attachments were created
        attachments = EnquiryAttachment.objects.filter(enquiry=enquiry)
        assert attachments.count() == 0
    
    def test_image_removal_preserves_order(self):
        """Test that removing images preserves the order of remaining images."""
        form_data = {
            'title': 'Test Enquiry',
            'description': 'Test Description',
            'member': self.member
        }
        
        # Simulate removing the middle image from a list of 5
        filtered_images = [
            {
                'original_filename': 'image1.jpg',
                'file_path': 'attachments/image1.jpg',
                'file_size': 1000
            },
            {
                'original_filename': 'image2.jpg',
                'file_path': 'attachments/image2.jpg',
                'file_size': 2000
            },
            # image3.jpg removed
            {
                'original_filename': 'image4.jpg',
                'file_path': 'attachments/image4.jpg',
                'file_size': 4000
            },
            {
                'original_filename': 'image5.jpg',
                'file_path': 'attachments/image5.jpg',
                'file_size': 5000
            }
        ]
        
        enquiry = EnquiryService.create_enquiry_with_attachments(
            form_data=form_data,
            user=self.admin_user,
            extracted_images_json=json.dumps(filtered_images)
        )
        
        # Verify correct number of attachments
        attachments = EnquiryAttachment.objects.filter(enquiry=enquiry).order_by('id')
        assert attachments.count() == 4
        
        # Verify the correct images were saved in order
        filenames = [att.filename for att in attachments]
        expected_filenames = ['image1.jpg', 'image2.jpg', 'image4.jpg', 'image5.jpg']
        assert filenames == expected_filenames
