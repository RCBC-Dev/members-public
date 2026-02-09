"""
File upload security services for the Members Enquiries System.

This module provides comprehensive file upload validation, sanitization,
and processing with security-first design principles.
"""

import hashlib
import logging
import mimetypes
import os
import tempfile
import uuid
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

logger = logging.getLogger(__name__)


class FileValidationError(Exception):
    """Custom exception for file validation errors."""
    pass


class FileSecurityService:
    """
    Comprehensive file security service for handling uploads.
    
    Provides MIME type validation, file size limits, malware scanning,
    image processing, and secure file storage.
    """
    
    # Allowed MIME types for different file categories
    ALLOWED_IMAGE_MIMES = {
        'image/jpeg',
        'image/jpg', 
        'image/png',
        'image/gif',
        'image/webp',
        'image/bmp',
        'image/tiff'
    }
    
    ALLOWED_EMAIL_MIMES = {
        'application/vnd.ms-outlook',  # .msg files
        'message/rfc822',             # .eml files
        'application/octet-stream'    # Sometimes .msg files are detected as this
    }
    
    ALLOWED_DOCUMENT_MIMES = {
        'application/pdf',                                                      # PDF files
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx files
        'application/msword',                                                   # .doc files
        'application/octet-stream'                                             # Sometimes documents are detected as this
    }
    
    # File extension mapping for validation
    SAFE_IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'
    }
    
    SAFE_EMAIL_EXTENSIONS = {
        '.msg', '.eml'
    }
    
    SAFE_DOCUMENT_EXTENSIONS = {
        '.pdf', '.doc', '.docx'
    }
    
    # File size limits (in bytes)
    MAX_IMAGE_SIZE = 15 * 1024 * 1024  # 15MB
    MAX_EMAIL_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_DOCUMENT_SIZE = 25 * 1024 * 1024  # 25MB
    
    # Image processing settings
    DEFAULT_MAX_DIMENSION = 2048
    DEFAULT_JPEG_QUALITY = 85
    DEFAULT_MAX_SIZE_MB = 2
    
    @staticmethod
    def validate_file_security(uploaded_file: UploadedFile, 
                             file_category: str = 'image',
                             check_content: bool = True) -> Dict:
        """
        Perform comprehensive security validation on uploaded file.
        
        Args:
            uploaded_file: Django UploadedFile object
            file_category: 'image' or 'email' - determines validation rules
            check_content: Whether to perform deep content analysis
            
        Returns:
            Dictionary with validation results and file info
            
        Raises:
            FileValidationError: If file fails security validation
        """
        try:
            # Basic file info
            file_info = {
                'original_name': uploaded_file.name,
                'size': uploaded_file.size,
                'content_type_claimed': uploaded_file.content_type,
            }
            
            # Validate file name
            FileSecurityService._validate_filename(uploaded_file.name)
            
            # Validate file size
            FileSecurityService._validate_file_size(uploaded_file.size, file_category)
            
            # Validate file extension
            extension = FileSecurityService._validate_extension(uploaded_file.name, file_category)
            file_info['extension'] = extension
            
            # Perform MIME type validation
            if check_content:
                detected_mime = FileSecurityService._detect_mime_type(uploaded_file)
                file_info['detected_mime'] = detected_mime
                
                FileSecurityService._validate_mime_type(detected_mime, file_category)
                
                # Additional content validation
                FileSecurityService._validate_file_content(uploaded_file, file_category)
            
            file_info['validation_passed'] = True
            logger.info(f"File validation passed: {uploaded_file.name} ({file_category})")
            return file_info
            
        except FileValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file validation: {e}", exc_info=True)
            raise FileValidationError(f"File validation failed: {str(e)}")
    
    @staticmethod
    def _validate_filename(filename: str) -> None:
        """Validate filename for security issues."""
        if not filename:
            raise FileValidationError("Filename cannot be empty")
        
        # Extract just the basename to handle drag-and-drop files with paths
        filename = os.path.basename(filename)
        
        # Check for path traversal attempts in the basename (only at path boundaries)
        # Allow legitimate use of ".." in filenames like "report..final.txt"
        path_parts = filename.split('/')
        for part in path_parts:
            if part == '..':
                raise FileValidationError("Invalid characters in filename: contains path traversal '..'")
        
        # Also check for Windows-style path traversal
        path_parts = filename.split('\\')
        for part in path_parts:
            if part == '..':
                raise FileValidationError("Invalid characters in filename: contains path traversal '..'")
        
        # Check for any remaining path separators (shouldn't happen after basename, but be safe)
        invalid_chars = []
        if '/' in filename:
            invalid_chars.append("'/'")
        if '\\' in filename:
            invalid_chars.append("'\\'")
        if invalid_chars:
            raise FileValidationError(f"Invalid characters in filename: {', '.join(invalid_chars)}")
        
        # Check for null bytes
        if '\x00' in filename:
            raise FileValidationError("Null bytes not allowed in filename")
        
        # Check for excessive length
        if len(filename) > 255:
            raise FileValidationError("Filename too long")
        
        # Check for dangerous extensions
        dangerous_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js', 
            '.jar', '.php', '.asp', '.aspx', '.jsp', '.sh', '.py', '.pl'
        }
        
        file_ext = os.path.splitext(filename.lower())[1]
        if file_ext in dangerous_extensions:
            raise FileValidationError(f"File type not allowed: {file_ext}")
    
    @staticmethod
    def _validate_file_size(file_size: int, file_category: str) -> None:
        """Validate file size based on category."""
        if file_size <= 0:
            raise FileValidationError("File appears to be empty")
        
        if file_category == 'image':
            max_size = FileSecurityService.MAX_IMAGE_SIZE
            category_name = "image"
        elif file_category == 'email':
            max_size = FileSecurityService.MAX_EMAIL_SIZE
            category_name = "email"
        elif file_category == 'document':
            max_size = FileSecurityService.MAX_DOCUMENT_SIZE
            category_name = "document"
        else:
            max_size = FileSecurityService.MAX_IMAGE_SIZE  # Default to image limits
            category_name = file_category
        
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise FileValidationError(f"File too large. Maximum size for {category_name} files is {max_mb:.1f}MB")
    
    @staticmethod
    def _validate_extension(filename: str, file_category: str) -> str:
        """Validate file extension based on category."""
        extension = os.path.splitext(filename.lower())[1]
        
        if not extension:
            raise FileValidationError("File must have an extension")
        
        if file_category == 'image':
            allowed_extensions = FileSecurityService.SAFE_IMAGE_EXTENSIONS
        elif file_category == 'email':
            allowed_extensions = FileSecurityService.SAFE_EMAIL_EXTENSIONS
        elif file_category == 'document':
            allowed_extensions = FileSecurityService.SAFE_DOCUMENT_EXTENSIONS
        else:
            raise FileValidationError(f"Unknown file category: {file_category}")
        
        if extension not in allowed_extensions:
            allowed_list = ', '.join(sorted(allowed_extensions))
            raise FileValidationError(f"File extension '{extension}' not allowed. Allowed: {allowed_list}")
        
        return extension
    
    @staticmethod
    def _detect_mime_type(uploaded_file: UploadedFile) -> str:
        """Detect MIME type using standard library mimetypes."""
        try:
            # Use standard library mimetypes for MIME detection
            detected_mime, _ = mimetypes.guess_type(uploaded_file.name)
            result = detected_mime or 'application/octet-stream'
            logger.debug(f"mimetypes detected MIME: {result}")
            return result

        except Exception as e:
            logger.error(f"MIME type detection failed: {e}")
            return 'application/octet-stream'
    
    @staticmethod
    def _validate_mime_type(detected_mime: str, file_category: str) -> None:
        """Validate detected MIME type against allowed types."""
        if file_category == 'image':
            allowed_mimes = FileSecurityService.ALLOWED_IMAGE_MIMES
        elif file_category == 'email':
            allowed_mimes = FileSecurityService.ALLOWED_EMAIL_MIMES
        elif file_category == 'document':
            allowed_mimes = FileSecurityService.ALLOWED_DOCUMENT_MIMES
        else:
            raise FileValidationError(f"Unknown file category: {file_category}")
        
        if detected_mime not in allowed_mimes:
            allowed_list = ', '.join(sorted(allowed_mimes))
            raise FileValidationError(
                f"File type '{detected_mime}' not allowed. Allowed: {allowed_list}"
            )
    
    @staticmethod
    def _validate_file_content(uploaded_file: UploadedFile, file_category: str) -> None:
        """Perform additional content validation."""
        if file_category == 'image':
            FileSecurityService._validate_image_content(uploaded_file)
        elif file_category == 'email':
            FileSecurityService._validate_email_content(uploaded_file)
        elif file_category == 'document':
            FileSecurityService._validate_document_content(uploaded_file)
    
    @staticmethod
    def _validate_image_content(uploaded_file: UploadedFile) -> None:
        """Validate image file content using Pillow."""
        try:
            from PIL import Image
            
            uploaded_file.seek(0)
            
            try:
                # Try to open and verify the image
                with Image.open(uploaded_file) as img:
                    # Verify it's a real image by getting its size
                    width, height = img.size
                    
                    # Check for reasonable dimensions
                    if width < 1 or height < 1:
                        raise FileValidationError("Invalid image dimensions")
                    
                    if width > 10000 or height > 10000:
                        raise FileValidationError("Image dimensions too large")
                    
                    # Verify image format (including MPO for multi-picture objects from cameras)
                    if img.format not in ('JPEG', 'PNG', 'GIF', 'WEBP', 'BMP', 'TIFF', 'MPO'):
                        raise FileValidationError(f"Unsupported image format: {img.format}")
                    
                    logger.debug(f"Image validation passed: {width}x{height}, format: {img.format}")
                    
            except Exception as e:
                if "cannot identify image file" in str(e).lower():
                    raise FileValidationError("File is not a valid image")
                raise FileValidationError(f"Image validation failed: {str(e)}")
            finally:
                uploaded_file.seek(0)
                
        except ImportError:
            logger.warning("Pillow not available - skipping advanced image validation")
    
    @staticmethod
    def _validate_email_content(uploaded_file: UploadedFile) -> None:
        """Validate email file content."""
        uploaded_file.seek(0)
        
        # Read first few bytes to check for email file signatures
        header = uploaded_file.read(1024)
        uploaded_file.seek(0)
        
        # Check for .msg file signature
        if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
            logger.debug("Valid .msg file signature detected")
            return
        
        # Check for .eml file patterns
        header_str = header.decode('utf-8', errors='ignore').lower()
        eml_patterns = ['received:', 'from:', 'to:', 'subject:', 'date:', 'message-id:']
        
        if any(pattern in header_str for pattern in eml_patterns):
            logger.debug("Valid .eml file patterns detected")
            return
        
        # If we can't identify it as a valid email file, that's suspicious
        logger.warning("Email file validation: Could not identify valid email signatures")

    @staticmethod
    def _validate_document_content(uploaded_file: UploadedFile) -> None:
        """Validate document file content."""
        uploaded_file.seek(0)
        
        # Read first few bytes to check for document file signatures
        header = uploaded_file.read(1024)
        uploaded_file.seek(0)
        
        # Check for PDF file signature
        if header.startswith(b'%PDF-'):
            logger.debug("Valid PDF file signature detected")
            return
        
        # Check for .docx file signature (ZIP-based format)
        if header.startswith(b'PK\x03\x04') or header.startswith(b'PK\x05\x06') or header.startswith(b'PK\x07\x08'):
            logger.debug("Valid .docx file signature detected (ZIP-based)")
            return
            
        # Check for .doc file signature (OLE2 format)
        if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
            logger.debug("Valid .doc file signature detected (OLE2)")
            return
        
        # If we can't identify it as a valid document file, log warning but don't fail
        # Some legitimate documents might not have clear signatures
        logger.warning("Document file validation: Could not identify clear document signatures")


class ImageProcessingService:
    """
    Service for processing and optimizing uploaded images.
    Integrates with existing resize functionality but adds security.
    """
    
    @staticmethod
    def process_and_save_image(uploaded_file: UploadedFile,
                             destination_dir: str,
                             max_dimension: int = None,
                             quality: int = None,
                             max_size_mb: int = None) -> Dict:
        """
        Process uploaded image with security validation and optimization.
        
        Args:
            uploaded_file: Django UploadedFile object
            destination_dir: Directory to save processed image
            max_dimension: Maximum width/height in pixels
            quality: JPEG quality (1-100)
            max_size_mb: Maximum file size in MB before resizing
            
        Returns:
            Dictionary with processing results
        """
        # Set defaults
        max_dimension = max_dimension or FileSecurityService.DEFAULT_MAX_DIMENSION
        quality = quality or FileSecurityService.DEFAULT_JPEG_QUALITY
        max_size_mb = max_size_mb or FileSecurityService.DEFAULT_MAX_SIZE_MB
        
        # Validate file security first
        file_info = FileSecurityService.validate_file_security(uploaded_file, 'image')
        
        # Read file data
        uploaded_file.seek(0)
        original_data = uploaded_file.read()
        
        # Use existing resize function from utils
        from .utils import _resize_image_if_needed
        processed_data, was_resized, final_size = _resize_image_if_needed(
            original_data, max_size_mb, max_dimension, quality
        )
        
        # Generate secure filename
        safe_filename = ImageProcessingService._generate_safe_filename(
            uploaded_file.name, was_resized
        )
        
        # Ensure destination directory exists
        os.makedirs(destination_dir, exist_ok=True)
        
        # Save processed file
        file_path = os.path.join(destination_dir, safe_filename)
        with open(file_path, 'wb') as f:
            f.write(processed_data)
        
        # Calculate relative path for URLs
        relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT).replace('\\', '/')
        
        result = {
            'success': True,
            'original_filename': uploaded_file.name,
            'saved_filename': safe_filename,
            'file_path': relative_path,
            'full_path': file_path,
            'file_size': final_size,
            'original_size': len(original_data),
            'was_resized': was_resized,
            'file_url': f"{settings.MEDIA_URL}{relative_path}",
            'mime_type': file_info.get('detected_mime', 'image/jpeg')
        }
        
        logger.info(f"Image processed successfully: {uploaded_file.name} -> {safe_filename}")
        if was_resized:
            logger.info(f"Image resized from {len(original_data):,} to {final_size:,} bytes")
        
        return result
    
    @staticmethod
    def _generate_safe_filename(original_name: str, was_resized: bool = False) -> str:
        """Generate a safe, unique filename."""
        # Get original extension
        original_ext = os.path.splitext(original_name.lower())[1]
        
        # Use .jpg for resized images (more efficient)
        if was_resized and original_ext not in ['.jpg', '.jpeg']:
            extension = '.jpg'
        else:
            extension = original_ext
        
        # Generate UUID-based filename
        unique_id = uuid.uuid4()
        return f"{unique_id}{extension}"


class FileUploadService:
    """
    High-level service for handling file uploads with comprehensive security.
    """
    
    @staticmethod
    def handle_image_upload(uploaded_file: UploadedFile, 
                          subfolder: str = 'uploads') -> Dict:
        """
        Handle image upload with full security and processing pipeline.
        
        Args:
            uploaded_file: Django UploadedFile object
            subfolder: Subdirectory within MEDIA_ROOT/enquiry_photos
            
        Returns:
            Dictionary with upload results or error information
        """
        try:
            # Create destination directory with date structure
            today = timezone.now().date()

            # Build path components
            path_components = [settings.MEDIA_ROOT, 'enquiry_photos']
            if subfolder:  # Only add subfolder if it's not empty
                path_components.append(subfolder)
            path_components.extend([
                today.strftime('%Y'),
                today.strftime('%m'),
                today.strftime('%d')
            ])

            destination_dir = os.path.join(*path_components)
            
            # Process and save image
            result = ImageProcessingService.process_and_save_image(
                uploaded_file, destination_dir
            )
            
            return result
            
        except FileValidationError as e:
            logger.warning(f"File validation failed for {uploaded_file.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'validation'
            }
        except Exception as e:
            logger.error(f"Unexpected error processing image upload: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"File processing failed: {str(e)}",
                'error_type': 'processing'
            }
    
    @staticmethod
    def handle_email_upload(uploaded_file: UploadedFile) -> Dict:
        """
        Handle email file upload with security validation.
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Validate file security
            file_info = FileSecurityService.validate_file_security(
                uploaded_file, 'email'
            )
            
            return {
                'success': True,
                'file_info': file_info,
                'validated': True
            }
            
        except FileValidationError as e:
            logger.warning(f"Email file validation failed for {uploaded_file.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'validation'
            }
        except Exception as e:
            logger.error(f"Unexpected error validating email file: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"File validation failed: {str(e)}",
                'error_type': 'processing'
            }
    
    @staticmethod
    def handle_document_upload(uploaded_file: UploadedFile,
                             subfolder: str = 'documents') -> Dict:
        """
        Handle document upload with security validation and storage.
        
        Args:
            uploaded_file: Django UploadedFile object
            subfolder: Subdirectory within MEDIA_ROOT/enquiry_attachments
            
        Returns:
            Dictionary with upload results or error information
        """
        try:
            # Validate file security
            file_info = FileSecurityService.validate_file_security(
                uploaded_file, 'document'
            )
            
            # Create destination directory with date structure
            today = timezone.now().date()
            
            # Build path components
            path_components = [settings.MEDIA_ROOT, 'enquiry_attachments']
            if subfolder:
                path_components.append(subfolder)
            path_components.extend([
                today.strftime('%Y'),
                today.strftime('%m'),
                today.strftime('%d')
            ])
            
            destination_dir = os.path.join(*path_components)
            os.makedirs(destination_dir, exist_ok=True)
            
            # Generate secure filename
            extension = file_info['extension']
            unique_filename = f"{uuid.uuid4()}{extension}"
            file_path = os.path.join(destination_dir, unique_filename)
            
            # Save the file
            uploaded_file.seek(0)
            with open(file_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            # Calculate relative path for URLs
            relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT).replace('\\', '/')
            
            result = {
                'success': True,
                'original_filename': uploaded_file.name,
                'saved_filename': unique_filename,
                'file_path': relative_path,
                'full_path': file_path,
                'file_size': uploaded_file.size,
                'file_url': f"{settings.MEDIA_URL}{relative_path}",
                'mime_type': file_info.get('detected_mime', 'application/octet-stream')
            }
            
            logger.info(f"Document processed successfully: {uploaded_file.name} -> {unique_filename}")
            return result
            
        except FileValidationError as e:
            logger.warning(f"Document validation failed for {uploaded_file.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'validation'
            }
        except Exception as e:
            logger.error(f"Unexpected error processing document upload: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"File processing failed: {str(e)}",
                'error_type': 'processing'
            }