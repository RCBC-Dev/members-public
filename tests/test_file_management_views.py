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
Tests for application/file_management_views.py
Comprehensive tests covering helper functions, ImageOptimizationStreamer,
and view endpoints.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from django.test import TestCase, Client, RequestFactory, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from application.models import Admin, EnquiryAttachment
from application.file_management_views import (
    format_file_size,
    _sanitize_directory,
    _get_file_attachment_info,
    _collect_directory_files,
    _collect_file_stats,
    _get_enquiry_ref,
    _get_enquiry_id,
    _build_missing_file_record,
    _build_corrupted_file_record,
    _check_image_integrity,
    _check_file_corruption,
    _process_attachment_size,
    _parse_optimization_params,
    ImageOptimizationStreamer,
)

# ===========================================================================
# Pure utility function tests (no Django DB required)
# ===========================================================================


class TestFormatFileSize:
    """Tests for format_file_size."""

    def test_zero_bytes(self):
        assert format_file_size(0) == "0 B"

    def test_bytes(self):
        assert format_file_size(500) == "500.0 B"

    def test_kilobytes(self):
        assert format_file_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_file_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_file_size(1024**3) == "1.0 GB"

    def test_terabytes(self):
        assert format_file_size(1024**4) == "1.0 TB"

    def test_fractional_kb(self):
        assert format_file_size(1536) == "1.5 KB"

    def test_fractional_mb(self):
        result = format_file_size(2 * 1024 * 1024 + 512 * 1024)
        assert result == "2.5 MB"

    def test_just_under_1kb(self):
        result = format_file_size(1023)
        assert "B" in result


class TestSanitizeDirectory:
    """Tests for _sanitize_directory."""

    def test_valid_enquiry_photos(self):
        directory, allowed = _sanitize_directory("enquiry_photos")
        assert directory == "enquiry_photos"
        assert "enquiry_photos" in allowed

    def test_valid_enquiry_attachments(self):
        directory, allowed = _sanitize_directory("enquiry_attachments")
        assert directory == "enquiry_attachments"

    def test_invalid_directory_defaults_to_photos(self):
        directory, allowed = _sanitize_directory("../../etc")
        assert directory == "enquiry_photos"

    def test_empty_string_defaults_to_photos(self):
        directory, _ = _sanitize_directory("")
        assert directory == "enquiry_photos"

    def test_allowed_dirs_always_returned(self):
        _, allowed = _sanitize_directory("anything")
        assert len(allowed) == 2
        assert "enquiry_photos" in allowed
        assert "enquiry_attachments" in allowed


class TestParseOptimizationParams:
    """Tests for _parse_optimization_params."""

    def test_defaults(self):
        request = MagicMock()
        request.method = "GET"
        request.GET = {}
        params = _parse_optimization_params(request)
        assert params["quality"] == 85
        assert params["dry_run"] is False
        assert params["min_size_mb"] == 1.0
        assert params["max_dimension"] == 1920

    def test_custom_values_from_get(self):
        request = MagicMock()
        request.method = "GET"
        request.GET = {
            "quality": "70",
            "dry_run": "true",
            "min_size_mb": "2.5",
            "max_dimension": "1280",
        }
        params = _parse_optimization_params(request)
        assert params["quality"] == 70
        assert params["dry_run"] is True
        assert params["min_size_mb"] == 2.5
        assert params["max_dimension"] == 1280

    def test_post_params(self):
        request = MagicMock()
        request.method = "POST"
        request.POST = {"quality": "90", "dry_run": "false"}
        params = _parse_optimization_params(request)
        assert params["quality"] == 90
        assert params["dry_run"] is False


# ===========================================================================
# Helper functions that use mock attachments
# ===========================================================================


class TestGetEnquiryRef:
    """Tests for _get_enquiry_ref."""

    def test_with_enquiry(self):
        attachment = MagicMock()
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-001"
        assert _get_enquiry_ref(attachment) == "ENQ-001"

    def test_without_enquiry(self):
        attachment = MagicMock()
        attachment.enquiry = None
        assert _get_enquiry_ref(attachment) == "N/A"


class TestGetEnquiryId:
    """Tests for _get_enquiry_id."""

    def test_with_enquiry(self):
        attachment = MagicMock()
        attachment.enquiry = MagicMock()
        attachment.enquiry.id = 42
        assert _get_enquiry_id(attachment) == 42

    def test_without_enquiry(self):
        attachment = MagicMock()
        attachment.enquiry = None
        assert _get_enquiry_id(attachment) is None


class TestBuildMissingFileRecord:
    """Tests for _build_missing_file_record."""

    def test_builds_complete_record(self):
        attachment = MagicMock()
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-002"
        attachment.enquiry.id = 5
        attachment.filename = "photo.jpg"
        attachment.file_path = "enquiry_photos/photo.jpg"
        attachment.uploaded_at = datetime(2026, 1, 15, 10, 30)
        attachment.file_size = 1024

        record = _build_missing_file_record(attachment)
        assert record["enquiry_ref"] == "ENQ-002"
        assert record["filename"] == "photo.jpg"
        assert record["file_path"] == "enquiry_photos/photo.jpg"
        assert record["uploaded_at"] == "2026-01-15 10:30"
        assert record["file_size"] == "1.0 KB"

    def test_unknown_file_size(self):
        attachment = MagicMock()
        attachment.enquiry = None
        attachment.filename = "doc.pdf"
        attachment.file_path = "enquiry_attachments/doc.pdf"
        attachment.uploaded_at = datetime(2026, 1, 15, 10, 30)
        attachment.file_size = None

        record = _build_missing_file_record(attachment)
        assert record["enquiry_ref"] == "N/A"
        assert record["file_size"] == "Unknown"


class TestBuildCorruptedFileRecord:
    """Tests for _build_corrupted_file_record."""

    def test_builds_record_with_reason(self):
        attachment = MagicMock()
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-003"
        attachment.enquiry.id = 10
        attachment.filename = "corrupt.jpg"
        attachment.file_path = "enquiry_photos/corrupt.jpg"
        attachment.uploaded_at = datetime(2026, 2, 1, 9, 0)

        record = _build_corrupted_file_record(attachment, "File is 0 bytes")
        assert record["reason"] == "File is 0 bytes"
        assert record["enquiry_ref"] == "ENQ-003"
        assert record["filename"] == "corrupt.jpg"


class TestCheckImageIntegrity:
    """Tests for _check_image_integrity."""

    def test_returns_none_when_pil_not_available(self):
        with patch("application.file_management_views.Image", None):
            assert _check_image_integrity("any_path") is None

    def test_valid_image_returns_none(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name
        try:
            # Create a small valid JPEG
            try:
                from PIL import Image as PILImage

                img = PILImage.new("RGB", (10, 10), color="red")
                img.save(temp_path, "JPEG")
                result = _check_image_integrity(temp_path)
                assert result is None
            except ImportError:
                pytest.skip("PIL not installed")
        finally:
            os.unlink(temp_path)

    def test_corrupt_file_returns_error(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"this is not a valid image file")
            temp_path = f.name
        try:
            try:
                from PIL import Image as PILImage  # noqa: F401

                result = _check_image_integrity(temp_path)
                assert result is not None
                assert "corrupted" in result.lower() or "image" in result.lower()
            except ImportError:
                pytest.skip("PIL not installed")
        finally:
            os.unlink(temp_path)


class TestCheckFileCorruption:
    """Tests for _check_file_corruption."""

    def test_zero_byte_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name
            # File is empty (0 bytes)
        try:
            attachment = MagicMock()
            attachment.enquiry = MagicMock()
            attachment.enquiry.reference = "ENQ-010"
            attachment.enquiry.id = 1
            attachment.filename = "empty.jpg"
            attachment.file_path = "enquiry_photos/empty.jpg"
            attachment.uploaded_at = datetime(2026, 1, 1, 0, 0)

            result = _check_file_corruption(Path(temp_path), attachment)
            assert result is not None
            assert "0 bytes" in result["reason"]
        finally:
            os.unlink(temp_path)

    def test_non_image_file_not_checked_for_corruption(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"some pdf content here")
            temp_path = f.name
        try:
            attachment = MagicMock()
            attachment.enquiry = None
            attachment.filename = "doc.pdf"
            attachment.file_path = "enquiry_attachments/doc.pdf"
            attachment.uploaded_at = datetime(2026, 1, 1, 0, 0)

            result = _check_file_corruption(Path(temp_path), attachment)
            assert result is None
        finally:
            os.unlink(temp_path)

    def test_unreadable_file(self):
        attachment = MagicMock()
        attachment.enquiry = None
        attachment.filename = "missing.jpg"
        attachment.file_path = "enquiry_photos/missing.jpg"
        attachment.uploaded_at = datetime(2026, 1, 1, 0, 0)

        # Use a path that exists but mock stat to raise
        fake_path = MagicMock(spec=Path)
        fake_path.stat.side_effect = PermissionError("No access")
        fake_path.suffix = ".jpg"

        result = _check_file_corruption(fake_path, attachment)
        assert result is not None
        assert "Cannot read file" in result["reason"]


class TestProcessAttachmentSize:
    """Tests for _process_attachment_size."""

    def test_matching_size_increments_matched(self):
        attachment = MagicMock()
        attachment.file_size = 5000
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-100"

        # Create a real temp file with known size
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 5000)
            temp_path = Path(f.name)
        try:
            stats = {
                "files_matched": 0,
                "files_updated": 0,
                "total_size_difference": 0,
                "details": [],
            }
            _process_attachment_size(attachment, temp_path, stats, dry_run=True)
            assert stats["files_matched"] == 1
            assert stats["files_updated"] == 0
        finally:
            os.unlink(temp_path)

    def test_mismatched_size_increments_updated(self):
        attachment = MagicMock()
        attachment.file_size = 100000  # DB says 100KB
        attachment.filename = "big.jpg"
        attachment.file_path = "enquiry_photos/big.jpg"
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-101"

        # Create file with different size
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 5000)  # Only 5KB on disk
            temp_path = Path(f.name)
        try:
            stats = {
                "files_matched": 0,
                "files_updated": 0,
                "total_size_difference": 0,
                "details": [],
            }
            _process_attachment_size(attachment, temp_path, stats, dry_run=True)
            assert stats["files_updated"] == 1
            assert len(stats["details"]) == 1
            assert stats["details"][0]["enquiry_ref"] == "ENQ-101"
        finally:
            os.unlink(temp_path)

    def test_dry_run_does_not_save(self):
        attachment = MagicMock()
        attachment.file_size = 100000
        attachment.filename = "test.jpg"
        attachment.file_path = "enquiry_photos/test.jpg"
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-102"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 5000)
            temp_path = Path(f.name)
        try:
            stats = {
                "files_matched": 0,
                "files_updated": 0,
                "total_size_difference": 0,
                "details": [],
            }
            _process_attachment_size(attachment, temp_path, stats, dry_run=True)
            attachment.save.assert_not_called()
        finally:
            os.unlink(temp_path)

    @patch("application.file_management_views.file_logger")
    def test_non_dry_run_saves_and_logs(self, mock_logger):
        attachment = MagicMock()
        attachment.file_size = 100000
        attachment.filename = "test.jpg"
        attachment.file_path = "enquiry_photos/test.jpg"
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-103"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 5000)
            temp_path = Path(f.name)
        try:
            stats = {
                "files_matched": 0,
                "files_updated": 0,
                "total_size_difference": 0,
                "details": [],
            }
            _process_attachment_size(attachment, temp_path, stats, dry_run=False)
            attachment.save.assert_called_once()
            mock_logger.log_size_update.assert_called_once()
        finally:
            os.unlink(temp_path)

    def test_unreadable_file_returns_silently(self):
        attachment = MagicMock()
        fake_path = MagicMock(spec=Path)
        fake_path.stat.side_effect = OSError("cannot read")

        stats = {
            "files_matched": 0,
            "files_updated": 0,
            "total_size_difference": 0,
            "details": [],
        }
        # Should not raise
        _process_attachment_size(attachment, fake_path, stats, dry_run=True)
        assert stats["files_matched"] == 0
        assert stats["files_updated"] == 0

    def test_details_capped_at_20(self):
        stats = {
            "files_matched": 0,
            "files_updated": 0,
            "total_size_difference": 0,
            "details": [{"dummy": i} for i in range(20)],
        }
        attachment = MagicMock()
        attachment.file_size = 100000
        attachment.filename = "test.jpg"
        attachment.file_path = "enquiry_photos/test.jpg"
        attachment.enquiry = MagicMock()
        attachment.enquiry.reference = "ENQ-104"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 5000)
            temp_path = Path(f.name)
        try:
            _process_attachment_size(attachment, temp_path, stats, dry_run=True)
            # Should still count the update but not add to details
            assert stats["files_updated"] == 1
            assert len(stats["details"]) == 20
        finally:
            os.unlink(temp_path)


# ===========================================================================
# Filesystem helper tests (using temp directories)
# ===========================================================================


class TestCollectDirectoryFiles:
    """Tests for _collect_directory_files."""

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "subdir"
            target.mkdir()
            with patch(
                "application.file_management_views.EnquiryAttachment"
            ) as mock_ea:
                mock_ea.objects.filter.return_value.first.return_value = None
                files = _collect_directory_files(target, Path(tmpdir))
            assert files == []

    def test_collects_files_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "enquiry_photos"
            target.mkdir()
            test_file = target / "test.jpg"
            test_file.write_bytes(b"x" * 2048)

            with patch(
                "application.file_management_views.EnquiryAttachment"
            ) as mock_ea:
                mock_ea.objects.filter.return_value.first.return_value = None
                files = _collect_directory_files(target, Path(tmpdir), iso_dates=False)

            assert len(files) == 1
            f = files[0]
            assert f["name"] == "test.jpg"
            assert f["size"] == 2048
            assert f["is_linked"] is False
            assert f["extension"] == ".jpg"
            assert isinstance(f["modified"], datetime)

    def test_iso_dates_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "photos"
            target.mkdir()
            (target / "a.png").write_bytes(b"img")

            with patch(
                "application.file_management_views.EnquiryAttachment"
            ) as mock_ea:
                mock_ea.objects.filter.return_value.first.return_value = None
                files = _collect_directory_files(target, Path(tmpdir), iso_dates=True)

            assert isinstance(files[0]["modified"], str)

    def test_nonexistent_directory(self):
        files = _collect_directory_files(Path("/nonexistent/dir"), Path("/nonexistent"))
        assert files == []


class TestGetFileAttachmentInfo:
    """Tests for _get_file_attachment_info."""

    @patch("application.file_management_views.EnquiryAttachment")
    def test_no_matching_attachment(self, mock_ea):
        mock_ea.objects.filter.return_value.first.return_value = None
        name, linked, ref, eid = _get_file_attachment_info(
            "enquiry_photos/test.jpg", "test.jpg"
        )
        assert name == "test.jpg"
        assert linked is False
        assert ref is None
        assert eid is None

    @patch("application.file_management_views.EnquiryAttachment")
    def test_matching_attachment_with_enquiry(self, mock_ea):
        mock_attachment = MagicMock()
        mock_attachment.filename = "original_name.jpg"
        mock_attachment.enquiry = MagicMock()
        mock_attachment.enquiry.reference = "ENQ-050"
        mock_attachment.enquiry.pk = 99
        mock_ea.objects.filter.return_value.first.return_value = mock_attachment

        name, linked, ref, eid = _get_file_attachment_info(
            "enquiry_photos/abc123.jpg", "abc123.jpg"
        )
        assert name == "original_name.jpg"
        assert linked is True
        assert ref == "ENQ-050"
        assert eid == 99

    @patch("application.file_management_views.EnquiryAttachment")
    def test_matching_attachment_without_enquiry(self, mock_ea):
        mock_attachment = MagicMock()
        mock_attachment.filename = "orphan.jpg"
        mock_attachment.enquiry = None
        mock_ea.objects.filter.return_value.first.return_value = mock_attachment

        name, linked, ref, eid = _get_file_attachment_info(
            "enquiry_photos/orphan.jpg", "orphan.jpg"
        )
        assert name == "orphan.jpg"
        assert linked is True
        assert ref is None
        assert eid is None


class TestCollectFileStats:
    """Tests for _collect_file_stats."""

    def test_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media_root = Path(tmpdir)
            photos = media_root / "enquiry_photos"
            photos.mkdir()
            (photos / "a.jpg").write_bytes(b"x" * 1000)
            (photos / "b.png").write_bytes(b"y" * 2000)

            date_stats, type_stats = _collect_file_stats(media_root)

            # Should have entries for both files
            total_files = sum(s["files"] for s in date_stats.values())
            assert total_files == 2

            assert ".jpg" in type_stats
            assert ".png" in type_stats
            assert type_stats[".jpg"]["files"] == 1
            assert type_stats[".png"]["files"] == 1

    def test_with_no_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            date_stats, type_stats = _collect_file_stats(Path(tmpdir))
            assert len(date_stats) == 0
            assert len(type_stats) == 0


# ===========================================================================
# ImageOptimizationStreamer tests
# ===========================================================================


class TestImageOptimizationStreamerInit:
    """Tests for ImageOptimizationStreamer initialization."""

    def test_default_init(self):
        streamer = ImageOptimizationStreamer(
            quality=85, dry_run=False, min_size_mb=1.0, max_dimension=1920
        )
        assert streamer.quality == 85
        assert streamer.dry_run is False
        assert streamer.min_size_bytes == 1024 * 1024
        assert streamer.max_dimension == 1920
        assert streamer.results["processed"] == 0
        assert streamer.results["errors"] == 0

    def test_custom_min_size(self):
        streamer = ImageOptimizationStreamer(
            quality=70, dry_run=True, min_size_mb=2.5, max_dimension=1280
        )
        assert streamer.min_size_bytes == int(2.5 * 1024 * 1024)
        assert streamer.dry_run is True


class TestSSEEvent:
    """Tests for _sse_event."""

    def test_formats_as_sse(self):
        result = ImageOptimizationStreamer._sse_event({"status": "ok"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        data = json.loads(result[6:].strip())
        assert data["status"] == "ok"


class TestCalculateResizeDimensions:
    """Tests for _calculate_resize_dimensions."""

    def test_landscape_image(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        w, h = streamer._calculate_resize_dimensions(3840, 2160)
        assert w == 1920
        assert h == int((2160 * 1920) / 3840)

    def test_portrait_image(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        w, h = streamer._calculate_resize_dimensions(1080, 3840)
        assert h == 1920
        assert w == int((1080 * 1920) / 3840)

    def test_square_image(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        w, h = streamer._calculate_resize_dimensions(4000, 4000)
        # Should use the else branch (height >= width), so h=1920
        assert h == 1920
        assert w == 1920


class TestCheckPNGNeedsOptimization:
    """Tests for _check_png_needs_optimization."""

    def test_large_dimensions(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_png_needs_optimization(3000, 2000, 500000, 0.08)
        assert needs is True
        assert "dimensions" in reason.lower()

    def test_large_file_size(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_png_needs_optimization(
            800, 600, 2 * 1024 * 1024, 4.37
        )
        assert needs is True
        assert "Large PNG" in reason

    def test_efficient_small_png(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_png_needs_optimization(100, 100, 5000, 0.3)
        assert needs is False
        assert "efficient" in reason.lower()

    def test_standard_png(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_png_needs_optimization(800, 600, 800000, 1.67)
        assert needs is True


class TestCheckJPEGNeedsOptimization:
    """Tests for _check_jpeg_needs_optimization."""

    def test_large_dimensions(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_jpeg_needs_optimization(
            3000, 2000, 500000, 0.08
        )
        assert needs is True
        assert "dimensions" in reason.lower()

    def test_large_file_size(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_jpeg_needs_optimization(
            800, 600, 3 * 1024 * 1024, 6.55
        )
        assert needs is True

    def test_well_compressed_small_jpeg(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_jpeg_needs_optimization(800, 600, 50000, 0.10)
        assert needs is False
        assert "well-compressed" in reason.lower()

    def test_standard_jpeg(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        needs, reason = streamer._check_jpeg_needs_optimization(800, 600, 1500000, 3.13)
        assert needs is True


class TestResizeIfNeeded:
    """Tests for _resize_if_needed."""

    def test_small_image_not_resized(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        mock_img = MagicMock()
        mock_img.size = (800, 600)

        img, resized, old_dims, new_dims, events = streamer._resize_if_needed(
            mock_img, "small.jpg"
        )
        assert resized is False
        assert old_dims is None
        assert new_dims is None
        assert events == []
        mock_img.resize.assert_not_called()

    def test_large_image_resized(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        mock_img = MagicMock()
        mock_img.size = (3840, 2160)

        with patch("application.file_management_views.Image") as mock_pil:
            mock_pil.Resampling.LANCZOS = "LANCZOS"
            img, resized, old_dims, new_dims, events = streamer._resize_if_needed(
                mock_img, "big.jpg"
            )

        assert resized is True
        assert old_dims == "3840x2160"
        assert len(events) == 1
        mock_img.resize.assert_called_once()


class TestBuildFinalResults:
    """Tests for _build_final_results."""

    def test_with_savings(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        streamer.results = {
            "processed": 5,
            "errors": 1,
            "total_size_before": 10 * 1024 * 1024,
            "total_size_after": 7 * 1024 * 1024,
            "error_files": [{"filename": "bad.jpg", "error": "oops"}],
        }
        event = streamer._build_final_results(6)
        data = json.loads(event[6:].strip())
        assert data["status"] == "complete"
        assert data["processed"] == 5
        assert data["errors"] == 1
        assert data["total_files"] == 6
        assert data["savings_percent"] == 30.0

    def test_with_zero_size_before(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        streamer.results = {
            "processed": 0,
            "errors": 0,
            "total_size_before": 0,
            "total_size_after": 0,
            "error_files": [],
        }
        event = streamer._build_final_results(0)
        data = json.loads(event[6:].strip())
        assert data["savings_percent"] == 0


class TestGenerateNoFilesMessage:
    """Tests for _generate_no_files_message."""

    def test_with_skipped_files(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        event = streamer._generate_no_files_message(10)
        data = json.loads(event[6:].strip())
        assert data["status"] == "complete"
        assert "10" in data["message"]
        assert "well-compressed" in data["message"] or "smaller" in data["message"]

    def test_with_no_files_at_all(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        event = streamer._generate_no_files_message(0)
        data = json.loads(event[6:].strip())
        assert "No image files found" in data["message"]


class TestHandleFileError:
    """Tests for _handle_file_error."""

    @patch("application.file_management_views.file_logger")
    @patch("application.file_management_views.settings")
    def test_records_error(self, mock_settings, mock_logger):
        mock_settings.MEDIA_ROOT = "/media"
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)

        file_path = MagicMock(spec=Path)
        file_path.name = "error.jpg"
        file_path.relative_to.return_value = Path("enquiry_photos/error.jpg")

        event = streamer._handle_file_error(file_path, Exception("test error"))

        assert streamer.results["errors"] == 1
        assert len(streamer.results["error_files"]) == 1
        data = json.loads(event[6:].strip())
        assert data["status"] == "file_error"
        assert data["filename"] == "error.jpg"
        mock_logger.log_error.assert_called_once()


class TestGenerateProgressNoPIL:
    """Tests for generate_progress when PIL is not available."""

    def test_no_pil_yields_error(self):
        streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
        with patch("application.file_management_views.Image", None):
            events = list(streamer.generate_progress())
        assert len(events) == 1
        data = json.loads(events[0][6:].strip())
        assert "Pillow" in data["error"]

    @patch("application.file_management_views.Image")
    @patch("application.file_management_views.settings")
    def test_no_image_dir_yields_error(self, mock_settings, mock_image):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings.MEDIA_ROOT = tmpdir
            # Don't create enquiry_photos dir
            streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
            events = list(streamer.generate_progress())

        # Should get error about no directory
        assert len(events) >= 1
        data = json.loads(events[0][6:].strip())
        assert "error" in data

    @patch("application.file_management_views.Image")
    @patch("application.file_management_views.settings")
    def test_empty_dir_yields_complete(self, mock_settings, mock_image):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings.MEDIA_ROOT = tmpdir
            photos_dir = Path(tmpdir) / "enquiry_photos"
            photos_dir.mkdir()

            streamer = ImageOptimizationStreamer(85, False, 1.0, 1920)
            events = list(streamer.generate_progress())

        # Should get scanning, starting, then complete with no-files message
        statuses = []
        for e in events:
            data = json.loads(e[6:].strip())
            if "status" in data:
                statuses.append(data["status"])
        assert "scanning" in statuses
        assert "complete" in statuses


# ===========================================================================
# View-level integration tests (with Django test client)
# ===========================================================================


class BaseFileManagementTest(TestCase):
    """Base class with admin user setup for file management tests."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="fmadmin", password="testpass123", email="fmadmin@test.com"
        )
        self.admin = Admin.objects.create(user=self.user)
        self.client.login(username="fmadmin", password="testpass123")


class TestUnauthenticatedFileMgmt(TestCase):
    """Test that file management views redirect without auth."""

    def test_file_management_dashboard_redirects(self):
        response = self.client.get(reverse("application:file_management_dashboard"))
        self.assertIn(response.status_code, [302, 301])

    def test_run_storage_analysis_redirects(self):
        response = self.client.get(reverse("application:run_storage_analysis"))
        self.assertIn(response.status_code, [302, 301])

    def test_file_browser_redirects(self):
        response = self.client.get(reverse("application:file_browser"))
        self.assertIn(response.status_code, [302, 301])

    def test_storage_analytics_api_redirects(self):
        response = self.client.get(reverse("application:storage_analytics_api"))
        self.assertIn(response.status_code, [302, 301])

    def test_check_missing_images_redirects(self):
        response = self.client.post(reverse("application:check_missing_images"))
        self.assertIn(response.status_code, [302, 301])

    def test_update_attachment_sizes_redirects(self):
        response = self.client.post(reverse("application:update_attachment_sizes"))
        self.assertIn(response.status_code, [302, 301])


class TestNonAdminAccess(TestCase):
    """Test that non-admin users cannot access file management views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="normaluser", password="testpass123", email="normal@test.com"
        )
        self.client.login(username="normaluser", password="testpass123")

    def test_dashboard_forbidden_for_non_admin(self):
        response = self.client.get(reverse("application:file_management_dashboard"))
        # Should redirect or return 403
        self.assertIn(response.status_code, [302, 403])


class TestFileDashboard(BaseFileManagementTest):
    """Tests for file_management_dashboard view."""

    def test_dashboard_loads(self):
        response = self.client.get(reverse("application:file_management_dashboard"))
        self.assertIn(response.status_code, [200, 302])

    def test_file_browser_loads(self):
        response = self.client.get(reverse("application:file_browser"))
        self.assertIn(response.status_code, [200, 302])

    def test_dashboard_only_allows_get(self):
        response = self.client.post(reverse("application:file_management_dashboard"))
        self.assertEqual(response.status_code, 405)


class TestRunStorageAnalysis(BaseFileManagementTest):
    """Tests for run_storage_analysis view."""

    def test_post_storage_analysis(self):
        response = self.client.post(reverse("application:run_storage_analysis"))
        self.assertIn(response.status_code, [200, 302])

    def test_get_not_allowed(self):
        response = self.client.get(reverse("application:run_storage_analysis"))
        self.assertEqual(response.status_code, 405)

    def test_storage_analysis_returns_json(self):
        response = self.client.post(reverse("application:run_storage_analysis"))
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("success", data)


class TestStorageAnalyticsApi(BaseFileManagementTest):
    """Tests for storage_analytics_api view."""

    def test_returns_json(self):
        response = self.client.get(reverse("application:storage_analytics_api"))
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("success", data)

    def test_post_not_allowed(self):
        response = self.client.post(reverse("application:storage_analytics_api"))
        self.assertEqual(response.status_code, 405)


class TestFileBrowser(BaseFileManagementTest):
    """Tests for file_browser view."""

    def test_default_directory(self):
        response = self.client.get(reverse("application:file_browser"))
        if response.status_code == 200:
            self.assertIn("enquiry_photos", response.context.get("directory", ""))

    def test_switch_directory(self):
        response = self.client.get(
            reverse("application:file_browser"), {"dir": "enquiry_attachments"}
        )
        if response.status_code == 200:
            self.assertEqual(response.context["directory"], "enquiry_attachments")

    def test_invalid_directory_defaults(self):
        response = self.client.get(
            reverse("application:file_browser"), {"dir": "../../etc"}
        )
        if response.status_code == 200:
            self.assertEqual(response.context["directory"], "enquiry_photos")


class TestFileBrowserData(BaseFileManagementTest):
    """Tests for file_browser_data view."""

    def test_returns_json(self):
        response = self.client.get(reverse("application:file_browser_data"))
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("data", data)
            self.assertIsInstance(data["data"], list)

    def test_invalid_directory_defaults(self):
        response = self.client.get(
            reverse("application:file_browser_data"),
            {"directory": "../../etc"},
        )
        # Should still work, defaulting to enquiry_photos
        self.assertIn(response.status_code, [200, 302])


class TestCheckMissingImages(BaseFileManagementTest):
    """Tests for check_missing_images view."""

    def test_returns_json(self):
        response = self.client.post(reverse("application:check_missing_images"))
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("success", data)
            self.assertIn("total_checked", data)
            self.assertIn("missing_count", data)

    def test_get_not_allowed(self):
        response = self.client.get(reverse("application:check_missing_images"))
        self.assertEqual(response.status_code, 405)


class TestUpdateAttachmentSizes(BaseFileManagementTest):
    """Tests for update_attachment_sizes view."""

    def test_get_not_allowed(self):
        response = self.client.get(reverse("application:update_attachment_sizes"))
        self.assertEqual(response.status_code, 405)

    def test_dry_run(self):
        response = self.client.post(
            reverse("application:update_attachment_sizes"),
            {"dry_run": "true"},
        )
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("success", data)
            self.assertIn("total_checked", data)

    def test_post_returns_json(self):
        response = self.client.post(reverse("application:update_attachment_sizes"))
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIsInstance(data, dict)


class TestCleanupOrphanedFiles(BaseFileManagementTest):
    """Tests for cleanup_orphaned_files view."""

    def test_get_not_allowed(self):
        response = self.client.get(reverse("application:cleanup_orphaned_files"))
        self.assertEqual(response.status_code, 405)

    def test_dry_run(self):
        response = self.client.post(
            reverse("application:cleanup_orphaned_files"),
            {"dry_run": "true"},
        )
        self.assertIn(response.status_code, [200, 302])

    def test_returns_json(self):
        response = self.client.post(
            reverse("application:cleanup_orphaned_files"),
            {"dry_run": "true"},
        )
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("success", data)


class TestOptimizeEnquiryImages(BaseFileManagementTest):
    """Tests for optimize_enquiry_images view."""

    def test_get_not_allowed(self):
        response = self.client.get(reverse("application:optimize_enquiry_images"))
        self.assertEqual(response.status_code, 405)

    def test_analyze_action(self):
        response = self.client.post(
            reverse("application:optimize_enquiry_images"),
            {"action": "analyze"},
        )
        self.assertIn(response.status_code, [200, 302])
