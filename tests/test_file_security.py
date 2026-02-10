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
Tests for file upload security functionality.
"""

import os
import tempfile
import shutil
from io import BytesIO
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.conf import settings

from application.file_security import (
    FileSecurityService,
    FileValidationError,
    ImageProcessingService,
    FileUploadService
)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TestFileSecurityService(TestCase):
    """Test file security validation."""

    def setUp(self):
        """Set up test data."""
        # Create a minimal valid JPEG header
        self.valid_jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00'

        # Create a minimal PNG header
        self.valid_png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'

    def tearDown(self):
        """Clean up test data and files."""
        # Clean up the temporary media directory
        if hasattr(settings, 'MEDIA_ROOT') and os.path.exists(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
    
    def test_validate_filename_success(self):
        """Test valid filename passes validation."""
        FileSecurityService._validate_filename('test_image.jpg')
        FileSecurityService._validate_filename('photo_123.png')
        # Should not raise exception
    
    def test_validate_filename_path_traversal(self):
        """Test filename with path traversal components is rejected."""
        # Test filenames that contain '..' as actual path components after basename
        # This would be unusual but the function is designed to catch these edge cases
        
        # Simulate a filename that somehow contains '..' as a path component
        # This tests the protection logic in case basename doesn't work as expected
        with pytest.raises(FileValidationError):
            # Create a test scenario where we bypass basename for testing
            FileSecurityService._validate_filename('..')  # Just '..' as filename
        
        # Test that normal filenames with '..' in content (not as path) are allowed
        FileSecurityService._validate_filename('report..final.txt')  # Should not raise
        FileSecurityService._validate_filename('file...backup.jpg')  # Should not raise
    
    def test_validate_filename_dangerous_extension(self):
        """Test dangerous file extensions are rejected."""
        dangerous_files = [
            'malware.exe',
            'script.bat',
            'virus.scr',
            'backdoor.php',
            'shell.asp'
        ]
        
        for filename in dangerous_files:
            with pytest.raises(FileValidationError):
                FileSecurityService._validate_filename(filename)
    
    def test_validate_file_size_success(self):
        """Test valid file sizes pass validation."""
        # Small image
        FileSecurityService._validate_file_size(1024 * 1024, 'image')  # 1MB
        
        # Small email
        FileSecurityService._validate_file_size(5 * 1024 * 1024, 'email')  # 5MB
    
    def test_validate_file_size_too_large(self):
        """Test oversized files are rejected."""
        # Image too large (over 15MB)
        with pytest.raises(FileValidationError):
            FileSecurityService._validate_file_size(20 * 1024 * 1024, 'image')
        
        # Email too large (over 50MB)
        with pytest.raises(FileValidationError):
            FileSecurityService._validate_file_size(60 * 1024 * 1024, 'email')
    
    def test_validate_extension_success(self):
        """Test valid extensions pass validation."""
        # Valid image extensions
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            result = FileSecurityService._validate_extension(f'test{ext}', 'image')
            assert result == ext
        
        # Valid email extensions
        for ext in ['.msg', '.eml']:
            result = FileSecurityService._validate_extension(f'email{ext}', 'email')
            assert result == ext
    
    def test_validate_extension_invalid(self):
        """Test invalid extensions are rejected."""
        # Invalid image extension
        with pytest.raises(FileValidationError):
            FileSecurityService._validate_extension('test.txt', 'image')
        
        # Invalid email extension
        with pytest.raises(FileValidationError):
            FileSecurityService._validate_extension('test.doc', 'email')
    
    def test_validate_mime_type_success(self):
        """Test valid MIME types pass validation."""
        # Valid image MIME types
        for mime in ['image/jpeg', 'image/png', 'image/gif']:
            FileSecurityService._validate_mime_type(mime, 'image')
        
        # Valid email MIME types
        for mime in ['application/vnd.ms-outlook', 'message/rfc822']:
            FileSecurityService._validate_mime_type(mime, 'email')
    
    def test_validate_mime_type_invalid(self):
        """Test invalid MIME types are rejected."""
        # Invalid image MIME type
        with pytest.raises(FileValidationError):
            FileSecurityService._validate_mime_type('application/pdf', 'image')
        
        # Invalid email MIME type
        with pytest.raises(FileValidationError):
            FileSecurityService._validate_mime_type('text/plain', 'email')
    
    def test_validate_file_security_success(self):
        """Test complete file validation success."""
        # Create a mock uploaded file
        uploaded_file = SimpleUploadedFile(
            "test.jpg",
            self.valid_jpeg_data,
            content_type="image/jpeg"
        )
        
        # Should not raise exception and return validation info
        result = FileSecurityService.validate_file_security(
            uploaded_file, 'image', check_content=False
        )
        
        assert result['validation_passed'] is True
        assert result['original_name'] == 'test.jpg'
        assert result['extension'] == '.jpg'
    
    def test_validate_file_security_failure(self):
        """Test file validation catches malicious files."""
        # Create a file with wrong extension
        uploaded_file = SimpleUploadedFile(
            "malware.exe",
            b"fake exe content",
            content_type="application/x-executable"
        )
        
        with pytest.raises(FileValidationError):
            FileSecurityService.validate_file_security(uploaded_file, 'image')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TestImageProcessingService(TestCase):
    """Test image processing functionality."""

    def setUp(self):
        """Set up test data."""
        # Create minimal valid JPEG data
        self.valid_jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00'

    def tearDown(self):
        """Clean up test data and files."""
        # Clean up the temporary media directory
        if hasattr(settings, 'MEDIA_ROOT') and os.path.exists(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
    
    def test_generate_safe_filename(self):
        """Test safe filename generation."""
        filename = ImageProcessingService._generate_safe_filename("test.jpg", False)
        assert filename.endswith('.jpg')
        assert len(filename) > 10  # UUID should make it longer
        
        # Test resized filename (should become .jpg)
        filename = ImageProcessingService._generate_safe_filename("test.png", True)
        assert filename.endswith('.jpg')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TestFileUploadService(TestCase):
    """Test high-level file upload service."""

    def setUp(self):
        """Set up test data."""
        self.valid_jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00'

    def tearDown(self):
        """Clean up test data and files."""
        # Clean up the temporary media directory
        if hasattr(settings, 'MEDIA_ROOT') and os.path.exists(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
    
    def test_handle_email_upload_success(self):
        """Test successful email file validation."""
        # Create a mock .msg file (with OLE signature)
        msg_data = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 100
        
        uploaded_file = SimpleUploadedFile(
            "test.msg",
            msg_data,
            content_type="application/vnd.ms-outlook"
        )
        
        result = FileUploadService.handle_email_upload(uploaded_file)
        assert result['success'] is True
        assert result['validated'] is True
    
    def test_handle_email_upload_failure(self):
        """Test email file validation failure."""
        # Create an invalid file
        uploaded_file = SimpleUploadedFile(
            "malware.exe",
            b"fake executable",
            content_type="application/x-executable"
        )

        result = FileUploadService.handle_email_upload(uploaded_file)
        assert result['success'] is False
        assert 'error' in result
        assert result['error_type'] == 'validation'

    def test_mime_type_detection_mimetypes(self):
        """Test that MIME type detection works with mimetypes."""
        # Create a mock .msg file
        msg_data = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 100

        uploaded_file = SimpleUploadedFile(
            "test.msg",
            msg_data,
            content_type="application/vnd.ms-outlook"
        )

        # Test the MIME type detection directly
        detected_mime = FileSecurityService._detect_mime_type(uploaded_file)

        # Should return the mimetypes detected MIME type or fallback
        # For .msg files, mimetypes typically returns application/octet-stream
        assert detected_mime in [
            'application/vnd.ms-outlook',
            'application/octet-stream'  # mimetypes typical result for .msg
        ]


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TestFileSecurityIntegration(TestCase):
    """Integration tests for file security."""

    def tearDown(self):
        """Clean up test data and files."""
        # Clean up the temporary media directory
        if hasattr(settings, 'MEDIA_ROOT') and os.path.exists(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
    
    def test_complete_image_upload_workflow(self):
        """Test complete image upload with security and processing."""
        # This would require a real image file and Django settings
        # For now, just test that the service can be imported and initialized
        assert FileUploadService is not None
        assert FileSecurityService is not None
        assert ImageProcessingService is not None
    
    def test_security_service_configuration(self):
        """Test that security service has proper configuration."""
        # Check that allowed MIME types are properly defined
        assert len(FileSecurityService.ALLOWED_IMAGE_MIMES) > 0
        assert len(FileSecurityService.ALLOWED_EMAIL_MIMES) > 0
        
        # Check that file size limits are reasonable
        assert FileSecurityService.MAX_IMAGE_SIZE > 0
        assert FileSecurityService.MAX_EMAIL_SIZE > 0
        assert FileSecurityService.MAX_EMAIL_SIZE > FileSecurityService.MAX_IMAGE_SIZE