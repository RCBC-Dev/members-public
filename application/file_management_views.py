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
File management views for administrative oversight of file storage.

This module provides views for:
- File storage analytics dashboard
- Orphaned file management
- Storage optimization tools
- File system health monitoring
"""

import os
import json
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from application.models import EnquiryAttachment
from application.utils import admin_required
from application.file_logger import file_logger


@login_required
@admin_required()
@require_http_methods(["GET"])
def file_management_dashboard(request):
    """
    Main file management dashboard showing storage analytics and tools.
    """
    # Get basic storage statistics
    media_root = Path(settings.MEDIA_ROOT)

    # Calculate directory sizes
    directory_stats = {}
    total_size = 0
    total_files = 0

    for directory_name in [
        "enquiry_photos",
        "enquiry_attachments",
    ]:
        directory_path = media_root / directory_name
        if directory_path.exists():
            dir_size = 0
            dir_files = 0

            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = Path(root) / file
                    try:
                        file_size = file_path.stat().st_size
                        dir_size += file_size
                        dir_files += 1
                    except OSError:
                        continue

            directory_stats[directory_name] = {
                "size": dir_size,
                "files": dir_files,
                "size_formatted": format_file_size(dir_size),
            }
            total_size += dir_size
            total_files += dir_files

    # Get database statistics
    db_attachments = EnquiryAttachment.objects.count()

    # Recent activity (files uploaded in last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_attachments = EnquiryAttachment.objects.filter(
        uploaded_at__gte=thirty_days_ago
    ).count()

    context = {
        "directory_stats": directory_stats,
        "total_size": total_size,
        "total_files": total_files,
        "total_size_formatted": format_file_size(total_size),
        "db_attachments": db_attachments,
        "recent_attachments": recent_attachments,
        "page_title": "File Management Dashboard",
    }

    return render(request, "admin/file_management_dashboard.html", context)


@login_required
@admin_required()
@require_http_methods(["POST"])
@csrf_protect
def run_storage_analysis(request):
    """
    Run comprehensive storage analysis and return results as JSON.
    """
    try:
        # Capture command output
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        # Run the analysis command
        call_command("analyze_file_storage", "--find-orphans")

        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()

        # Parse the output for key metrics
        lines = output.split("\n")
        metrics = {}

        for line in lines:
            if "Total files:" in line:
                metrics["total_files"] = line.split(":")[1].strip()
            elif "Total size:" in line:
                metrics["total_size"] = line.split(":")[1].strip()
            elif "Found" in line and "orphaned files" in line:
                parts = line.split()
                if len(parts) >= 2:
                    metrics["orphaned_files"] = parts[1]
                    # Extract size from parentheses
                    if "(" in line and ")" in line:
                        size_part = line[line.find("(") + 1 : line.find(")")]
                        metrics["orphaned_size"] = size_part

        return JsonResponse({"success": True, "metrics": metrics, "output": output})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required()
@require_http_methods(["POST"])
@csrf_protect
def cleanup_orphaned_files(request):
    """
    Clean up orphaned files with backup option.
    """
    try:
        backup = request.POST.get("backup", "true").lower() == "true"
        dry_run = request.POST.get("dry_run", "false").lower() == "true"

        # Capture command output
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        # Build command arguments
        args = []
        if backup:
            args.append("--backup")
        if dry_run:
            args.append("--dry-run")
        else:
            args.append("--confirm")

        # Run the cleanup command
        call_command("cleanup_orphaned_files", *args)

        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()

        # Parse results
        metrics = {}
        for line in output.split("\n"):
            if "Files deleted:" in line:
                metrics["deleted_files"] = line.split(":")[1].strip()
            elif "Space freed:" in line:
                metrics["space_freed"] = line.split(":")[1].strip()
            elif "Files backed up:" in line:
                metrics["backed_up"] = line.split(":")[1].strip()

        return JsonResponse(
            {"success": True, "metrics": metrics, "output": output, "dry_run": dry_run}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@admin_required()
@require_http_methods(["POST"])
@csrf_protect
def optimize_enquiry_images(request):
    """
    Optimize enquiry images for better storage efficiency.
    """
    try:
        action = request.POST.get("action", "analyze")
        quality = int(request.POST.get("quality", 85))
        dry_run = request.POST.get("dry_run", "false").lower() == "true"

        # Capture command output
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        # Build command arguments
        args = []
        if action == "analyze":
            args.append("--analyze")
        elif action == "compress":
            args.extend(["--compress", "--quality", str(quality)])
            if dry_run:
                args.append("--dry-run")

        # Run the optimization command
        call_command("optimize_enquiry_images", *args)

        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()

        return JsonResponse(
            {"success": True, "output": output, "action": action, "dry_run": dry_run}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Image optimization streaming - refactored into a class to reduce complexity
# ---------------------------------------------------------------------------


class ImageOptimizationStreamer:
    """Handles streaming image optimization with progress updates via SSE."""

    def __init__(self, quality, dry_run, min_size_mb, max_dimension):
        self.quality = quality
        self.dry_run = dry_run
        self.min_size_mb = min_size_mb
        self.min_size_bytes = min_size_mb * 1024 * 1024
        self.max_dimension = max_dimension
        self.results = {
            "processed": 0,
            "errors": 0,
            "total_size_before": 0,
            "total_size_after": 0,
            "error_files": [],
        }

    @staticmethod
    def _sse_event(data):
        """Format a dict as a Server-Sent Event data line."""
        return f"data: {json.dumps(data)}\n\n"

    # -- Scanning / analysis helpers ----------------------------------------

    def _check_png_needs_optimization(self, width, height, file_size, bytes_per_pixel):
        """Determine whether a PNG file needs optimization."""
        if width > self.max_dimension or height > self.max_dimension:
            return (
                True,
                f"Large PNG dimensions ({width}x{height}) need resizing/conversion",
            )

        if file_size > 1024 * 1024:
            return (
                True,
                f"Large PNG file ({format_file_size(file_size)}) needs optimization",
            )

        if bytes_per_pixel < 0.5 and file_size < 500 * 1024:
            return False, "PNG already very efficient and small"

        return True, "PNG will be analyzed for optimization"

    def _check_jpeg_needs_optimization(self, width, height, file_size, bytes_per_pixel):
        """Determine whether a JPEG file needs optimization."""
        if width > self.max_dimension or height > self.max_dimension:
            return True, f"Large dimensions ({width}x{height}) need resizing"

        if file_size > 2 * 1024 * 1024:
            return (
                True,
                f"Large file size ({format_file_size(file_size)}) needs compression",
            )

        if bytes_per_pixel < 0.15 and file_size < 1024 * 1024:
            return False, "JPEG already very well-compressed and reasonably sized"

        return True, "Will attempt optimization"

    def _analyze_file_for_optimization(self, file_path, filename, file_size):
        """Analyze a single image file to decide if it needs optimization.

        Returns (needs_optimization: bool, skip_reason: str).
        """
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                pixels = width * height
                bytes_per_pixel = file_size / pixels if pixels > 0 else 0

                if filename.lower().endswith(".png"):
                    needs, reason = self._check_png_needs_optimization(
                        width, height, file_size, bytes_per_pixel
                    )
                else:
                    needs, reason = self._check_jpeg_needs_optimization(
                        width, height, file_size, bytes_per_pixel
                    )

                self._log_analysis(
                    filename, needs, reason, width, height, file_size, bytes_per_pixel
                )
                return needs, reason

        except Exception as e:
            print(f"DEBUG: Cannot analyze {filename}: {e}")
            return True, ""

    @staticmethod
    def _log_analysis(filename, needs, reason, width, height, file_size, bpp):
        """Print debug log for optimization analysis."""
        action = "WILL OPTIMIZE" if needs else "SKIPPING"
        print(
            f"DEBUG: {action} {filename}: {reason} "
            f"({width}x{height}, {format_file_size(file_size)}, {bpp:.2f} bytes/pixel)"
        )

    def _scan_image_files(self, image_dir):
        """Walk the image directory and classify files into candidates and skipped.

        Returns (image_files, total_files, skipped_files).
        """
        image_files = []
        total_files = 0
        skipped_files = 0

        for root, dirs, files in os.walk(image_dir):
            for filename in files:
                if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue

                file_path = Path(root) / filename
                try:
                    file_size = file_path.stat().st_size
                except OSError:
                    continue

                if file_size <= self.min_size_bytes:
                    skipped_files += 1
                    continue

                needs_optimization, _ = self._analyze_file_for_optimization(
                    file_path, filename, file_size
                )

                if not needs_optimization:
                    skipped_files += 1
                    continue

                image_files.append(file_path)
                total_files += 1

        return image_files, total_files, skipped_files

    # -- Image processing helpers -------------------------------------------

    def _calculate_resize_dimensions(self, original_width, original_height):
        """Calculate new dimensions maintaining aspect ratio."""
        if original_width > original_height:
            new_width = self.max_dimension
            new_height = int((original_height * self.max_dimension) / original_width)
        else:
            new_height = self.max_dimension
            new_width = int((original_width * self.max_dimension) / original_height)
        return new_width, new_height

    def _resize_if_needed(self, img, filename):
        """Resize image if it exceeds max_dimension. Returns (img, resized, old_dims, new_dims, events)."""
        original_width, original_height = img.size
        events = []

        if (
            original_width <= self.max_dimension
            and original_height <= self.max_dimension
        ):
            return img, False, None, None, events

        new_width, new_height = self._calculate_resize_dimensions(
            original_width, original_height
        )
        old_dimensions = f"{original_width}x{original_height}"
        new_dimensions = f"{new_width}x{new_height}"

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        events.append(
            self._sse_event(
                {
                    "status": "file_resized",
                    "filename": filename,
                    "old_size": old_dimensions,
                    "new_size": new_dimensions,
                }
            )
        )

        return img, True, old_dimensions, new_dimensions, events

    def _convert_png_to_jpeg(self, img, file_path, filename):
        """Convert a PNG image to JPEG, updating the database. Returns (new_file_path, events)."""
        events = []
        old_relative_path = str(file_path.relative_to(settings.MEDIA_ROOT)).replace(
            "\\", "/"
        )
        attachment_to_update = EnquiryAttachment.objects.filter(
            file_path=old_relative_path
        ).first()

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        new_path = file_path.with_suffix(".jpg")
        img.save(new_path, "JPEG", optimize=True, quality=self.quality)

        if attachment_to_update:
            self._update_db_for_png_conversion(
                attachment_to_update, new_path, old_relative_path
            )
            file_path.unlink()
            events.append(
                self._sse_event(
                    {
                        "status": "file_converted",
                        "filename": filename,
                        "new_format": "JPEG",
                    }
                )
            )
        else:
            file_path.unlink()
            events.append(
                self._sse_event(
                    {
                        "status": "file_converted",
                        "filename": filename,
                        "new_format": "JPEG",
                        "warning": "No database record found",
                    }
                )
            )

        return new_path, events

    @staticmethod
    def _update_db_for_png_conversion(attachment, new_path, old_relative_path):
        """Update the database record when converting PNG to JPEG."""
        new_relative_path = str(new_path.relative_to(settings.MEDIA_ROOT)).replace(
            "\\", "/"
        )
        new_filename = new_path.name

        attachment.file_path = new_relative_path
        attachment.filename = new_filename
        attachment.save(update_fields=["file_path", "filename"])

        try:
            file_logger.log_move(
                old_path=old_relative_path,
                new_path=new_relative_path,
                reason="PNG->JPEG conversion for compression",
            )
        except Exception:
            pass  # Don't let logging errors prevent file cleanup

    def _optimize_png_image(self, img, file_path, filename, original_size):
        """Optimize a PNG image - convert to JPEG if beneficial, else optimize in-place.

        Returns (updated_file_path, events).
        """
        has_transparency = img.mode in ("RGBA", "LA") or "transparency" in img.info

        if not has_transparency and original_size > 1024 * 1024:
            return self._convert_png_to_jpeg(img, file_path, filename)

        # Keep as PNG but optimize
        img.save(file_path, "PNG", optimize=True)
        return file_path, []

    def _optimize_jpeg_image(self, img, file_path):
        """Optimize a JPEG image with compression."""
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(
                img,
                mask=img.split()[-1] if img.mode == "RGBA" else None,
            )
            img = background

        img.save(file_path, "JPEG", optimize=True, quality=self.quality)

    def _log_optimization_results(
        self,
        file_path,
        original_size,
        new_size,
        resized,
        old_dimensions,
        new_dimensions,
    ):
        """Log optimization results for a processed file."""
        relative_path = str(file_path.relative_to(settings.MEDIA_ROOT)).replace(
            "\\", "/"
        )
        attachment = EnquiryAttachment.objects.filter(file_path=relative_path).first()

        if not attachment:
            return

        enquiry_ref = attachment.enquiry.reference if attachment.enquiry else None

        if resized:
            file_logger.log_resize(
                file_path=relative_path,
                old_dimensions=old_dimensions,
                new_dimensions=new_dimensions,
                enquiry_ref=enquiry_ref,
            )

        savings_percent = (
            round((original_size - new_size) / original_size * 100, 1)
            if original_size > 0
            else 0
        )
        file_logger.log_compression(
            file_path=relative_path,
            original_size=format_file_size(original_size),
            new_size=format_file_size(new_size),
            savings_percent=savings_percent,
            enquiry_ref=enquiry_ref,
        )

        if attachment.file_size != new_size:
            old_db_size = attachment.file_size
            attachment.file_size = new_size
            attachment.save(update_fields=["file_size"])
            file_logger.log_size_update(
                file_path=relative_path,
                old_size=old_db_size,
                new_size=new_size,
                enquiry_ref=enquiry_ref,
            )

    def _process_image_optimization(self, img, file_path, filename, original_size):
        """Run the actual optimization on an opened image.

        Returns (updated_file_path, resized, old_dims, new_dims, events).
        """
        img, resized, old_dims, new_dims, events = self._resize_if_needed(img, filename)

        is_png = filename.lower().endswith(".png")
        if is_png:
            file_path, convert_events = self._optimize_png_image(
                img, file_path, filename, original_size
            )
            events.extend(convert_events)
        else:
            self._optimize_jpeg_image(img, file_path)

        return file_path, resized, old_dims, new_dims, events

    def _process_single_file(self, file_path, index, total_files):
        """Process a single image file. Yields SSE events."""
        filename = file_path.name
        progress_percent = round((index / total_files) * 100, 1)
        yield self._sse_event(
            {
                "status": "processing",
                "current_file": filename,
                "progress": index,
                "total": total_files,
                "percent": progress_percent,
            }
        )

        original_size = file_path.stat().st_size
        self.results["total_size_before"] += original_size

        if self.dry_run:
            new_size = int(original_size * (self.quality / 100))
        else:
            with Image.open(file_path) as img:
                file_path, resized, old_dims, new_dims, events = (
                    self._process_image_optimization(
                        img, file_path, filename, original_size
                    )
                )
            for event in events:
                yield event

            new_size = file_path.stat().st_size
            self._log_optimization_results(
                file_path,
                original_size,
                new_size,
                resized,
                old_dims,
                new_dims,
            )

        self.results["total_size_after"] += new_size
        self.results["processed"] += 1

        file_savings = original_size - new_size
        file_savings_percent = (
            (file_savings / original_size * 100) if original_size > 0 else 0
        )
        yield self._sse_event(
            {
                "status": "file_complete",
                "filename": filename,
                "original_size": original_size,
                "new_size": new_size,
                "savings": file_savings,
                "savings_percent": round(file_savings_percent, 1),
                "original_formatted": format_file_size(original_size),
                "new_formatted": format_file_size(new_size),
                "savings_formatted": format_file_size(file_savings),
            }
        )

    def _handle_file_error(self, file_path, error):
        """Record an error for a file and yield an SSE error event."""
        self.results["errors"] += 1
        self.results["error_files"].append(
            {"filename": file_path.name, "error": str(error)}
        )
        relative_path = str(file_path.relative_to(settings.MEDIA_ROOT)).replace(
            "\\", "/"
        )
        file_logger.log_error(
            operation="COMPRESS", file_path=relative_path, error_msg=str(error)
        )
        return self._sse_event(
            {
                "status": "file_error",
                "filename": file_path.name,
                "error": str(error),
            }
        )

    def _build_final_results(self, total_files):
        """Build and return the final results SSE event."""
        savings = self.results["total_size_before"] - self.results["total_size_after"]
        savings_percent = (
            (savings / self.results["total_size_before"] * 100)
            if self.results["total_size_before"] > 0
            else 0
        )
        return self._sse_event(
            {
                "status": "complete",
                "processed": self.results["processed"],
                "errors": self.results["errors"],
                "total_files": total_files,
                "savings_bytes": savings,
                "savings_percent": round(savings_percent, 1),
                "total_size_before": self.results["total_size_before"],
                "total_size_after": self.results["total_size_after"],
                "total_size_before_formatted": format_file_size(
                    self.results["total_size_before"]
                ),
                "total_size_after_formatted": format_file_size(
                    self.results["total_size_after"]
                ),
                "savings_formatted": format_file_size(savings),
                "error_files": self.results["error_files"],
                "dry_run": self.dry_run,
            }
        )

    def _generate_no_files_message(self, skipped_files):
        """Generate the completion message when no files need optimization."""
        if skipped_files > 0:
            msg = (
                f"No optimization needed! Found {skipped_files} images, "
                f"but all are either smaller than {self.min_size_mb}MB "
                f"or already well-compressed."
            )
        else:
            msg = "No image files found to optimize"
        return self._sse_event({"status": "complete", "message": msg})

    def generate_progress(self):
        """Generator function for streaming progress updates."""
        try:
            print(
                f"DEBUG: Starting optimization with quality={self.quality}, "
                f"dry_run={self.dry_run}, min_size_mb={self.min_size_mb}"
            )

            if Image is None:
                yield self._sse_event(
                    {
                        "error": "PIL (Pillow) is not installed. Please install it with: pip install Pillow"
                    }
                )
                return

            enquiry_photos_dir = Path(settings.MEDIA_ROOT) / "enquiry_photos"
            if not enquiry_photos_dir.exists():
                yield self._sse_event(
                    {"error": "No image directory found (enquiry_photos)"}
                )
                return

            yield self._sse_event(
                {
                    "status": "scanning",
                    "message": "Scanning enquiry images for optimization candidates...",
                }
            )

            image_files, total_files, skipped_files = self._scan_image_files(
                enquiry_photos_dir
            )

            yield self._sse_event(
                {
                    "status": "starting",
                    "total_files": total_files,
                    "skipped_files": skipped_files,
                    "min_size_mb": self.min_size_mb,
                    "dry_run": self.dry_run,
                }
            )

            if total_files == 0:
                yield self._generate_no_files_message(skipped_files)
                return

            for i, file_path in enumerate(image_files, 1):
                try:
                    yield from self._process_single_file(file_path, i, total_files)
                except Exception as e:
                    yield self._handle_file_error(file_path, e)

            yield self._build_final_results(total_files)

        except Exception as e:
            yield self._sse_event({"status": "error", "error": str(e)})


def _parse_optimization_params(request):
    """Extract optimization parameters from a GET or POST request."""
    params = request.GET if request.method == "GET" else request.POST
    return {
        "quality": int(params.get("quality", 85)),
        "dry_run": params.get("dry_run", "false").lower() == "true",
        "min_size_mb": float(params.get("min_size_mb", 1.0)),
        "max_dimension": int(params.get("max_dimension", 1920)),
    }


@login_required
@admin_required()
@require_http_methods(["GET", "POST"])
def optimize_enquiry_images_stream(request):
    """
    Stream real-time progress for enquiry image optimization.
    """
    params = _parse_optimization_params(request)
    streamer = ImageOptimizationStreamer(**params)

    # Return streaming response
    from django.http import StreamingHttpResponse

    response = StreamingHttpResponse(
        streamer.generate_progress(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disable nginx buffering
    # Note: Connection header removed for Django dev server compatibility
    return response


# ---------------------------------------------------------------------------
# File browser helpers
# ---------------------------------------------------------------------------


def _get_file_attachment_info(normalized_path, filename):
    """Look up the attachment record and return display metadata.

    Returns (display_name, is_linked, enquiry_ref, enquiry_id).
    """
    attachment = EnquiryAttachment.objects.filter(file_path=normalized_path).first()

    if not attachment:
        return filename, False, None, None

    display_name = attachment.filename
    enquiry_ref = None
    enquiry_id = None

    if attachment.enquiry:
        enquiry_ref = attachment.enquiry.reference
        enquiry_id = attachment.enquiry.pk

    return display_name, True, enquiry_ref, enquiry_id


def _collect_directory_files(target_dir, media_root, iso_dates=False):
    """Walk a directory and collect file metadata dicts.

    When *iso_dates* is True the 'modified' value is an ISO string;
    otherwise it is a datetime object.
    """
    files = []
    if not target_dir.exists():
        return files

    for root, dirs, filenames in os.walk(target_dir):
        for filename in filenames:
            file_path = Path(root) / filename
            try:
                stat = file_path.stat()
            except OSError:
                continue

            relative_path = file_path.relative_to(media_root)
            normalized_path = str(relative_path).replace("\\", "/")

            display_name, is_linked, enquiry_ref, enquiry_id = (
                _get_file_attachment_info(normalized_path, filename)
            )

            modified_val = datetime.fromtimestamp(stat.st_mtime)
            if iso_dates:
                modified_val = modified_val.isoformat()

            files.append(
                {
                    "name": filename,
                    "display_name": display_name,
                    "path": str(relative_path),
                    "size": stat.st_size,
                    "size_formatted": format_file_size(stat.st_size),
                    "modified": modified_val,
                    "is_linked": is_linked,
                    "extension": file_path.suffix.lower(),
                    "enquiry_ref": enquiry_ref,
                    "enquiry_id": enquiry_id,
                }
            )

    return files


def _sanitize_directory(directory):
    """Validate and return the requested directory, defaulting to enquiry_photos."""
    allowed_dirs = ["enquiry_photos", "enquiry_attachments"]
    if directory not in allowed_dirs:
        return "enquiry_photos", allowed_dirs
    return directory, allowed_dirs


@login_required
@admin_required()
@require_http_methods(["GET"])
def file_browser(request):
    """
    Browse files in the media directory with DataTables interface.
    """
    directory, allowed_dirs = _sanitize_directory(
        request.GET.get("dir", "enquiry_photos")
    )

    media_root = Path(settings.MEDIA_ROOT)
    target_dir = media_root / directory

    files = _collect_directory_files(target_dir, media_root, iso_dates=False)

    # Convert datetime objects to strings for JSON serialization
    files_json = []
    for file in files:
        file_copy = file.copy()
        file_copy["modified"] = file["modified"].isoformat()
        files_json.append(file_copy)

    context = {
        "directory": directory,
        "allowed_dirs": allowed_dirs,
        "page_title": f"File Browser - {directory}",
        "files_count": len(files),
        "files_json": json.dumps(files_json),  # Send all files as JSON for DataTables
    }

    return render(request, "admin/file_browser.html", context)


@login_required
@admin_required()
@require_http_methods(["GET"])
def file_browser_data(request):
    """
    DataTables-compatible API endpoint for file browser data.
    """
    directory, _ = _sanitize_directory(request.GET.get("directory", "enquiry_photos"))

    media_root = Path(settings.MEDIA_ROOT)
    target_dir = media_root / directory

    files = _collect_directory_files(target_dir, media_root, iso_dates=True)

    # Return DataTables-compatible JSON
    return JsonResponse({"data": files})


# ---------------------------------------------------------------------------
# Storage analytics helpers
# ---------------------------------------------------------------------------


def _collect_file_stats(media_root):
    """Walk media directories and gather date and file-type statistics.

    Returns (date_stats, file_type_stats) as defaultdicts.
    """
    date_stats = defaultdict(lambda: {"files": 0, "size": 0})
    file_type_stats = defaultdict(lambda: {"files": 0, "size": 0})

    for directory_name in ["enquiry_photos", "enquiry_attachments"]:
        directory_path = media_root / directory_name
        if not directory_path.exists():
            continue

        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = Path(root) / file
                try:
                    stat = file_path.stat()
                except OSError:
                    continue

                file_date = datetime.fromtimestamp(stat.st_mtime).date()
                file_ext = file_path.suffix.lower()

                date_stats[str(file_date)]["files"] += 1
                date_stats[str(file_date)]["size"] += stat.st_size

                file_type_stats[file_ext]["files"] += 1
                file_type_stats[file_ext]["size"] += stat.st_size

    return date_stats, file_type_stats


@login_required
@admin_required()
@require_http_methods(["GET"])
def storage_analytics_api(request):
    """
    API endpoint for storage analytics data (for charts and graphs).
    """
    try:
        media_root = Path(settings.MEDIA_ROOT)
        date_stats, file_type_stats = _collect_file_stats(media_root)

        date_data = [
            {
                "date": date,
                "files": stats["files"],
                "size": stats["size"],
                "size_formatted": format_file_size(stats["size"]),
            }
            for date, stats in sorted(date_stats.items())
        ]

        file_type_data = [
            {
                "extension": ext or "no extension",
                "files": stats["files"],
                "size": stats["size"],
                "size_formatted": format_file_size(stats["size"]),
            }
            for ext, stats in sorted(
                file_type_stats.items(), key=lambda x: x[1]["size"], reverse=True
            )
        ]

        return JsonResponse(
            {
                "success": True,
                "date_data": date_data[-30:],  # Last 30 days
                "file_type_data": file_type_data[:10],  # Top 10 file types
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Missing images check helpers
# ---------------------------------------------------------------------------


def _get_enquiry_ref(attachment):
    """Return the enquiry reference string or 'N/A'."""
    if attachment.enquiry:
        return attachment.enquiry.reference
    return "N/A"


def _get_enquiry_id(attachment):
    """Return the enquiry id or None."""
    if attachment.enquiry:
        return attachment.enquiry.id
    return None


def _build_missing_file_record(attachment):
    """Build a dict describing a missing attachment file."""
    return {
        "enquiry_ref": _get_enquiry_ref(attachment),
        "enquiry_id": _get_enquiry_id(attachment),
        "filename": attachment.filename,
        "file_path": attachment.file_path,
        "uploaded_at": attachment.uploaded_at.strftime("%Y-%m-%d %H:%M"),
        "file_size": (
            format_file_size(attachment.file_size)
            if attachment.file_size
            else "Unknown"
        ),
    }


def _build_corrupted_file_record(attachment, reason):
    """Build a dict describing a corrupted attachment file."""
    return {
        "enquiry_ref": _get_enquiry_ref(attachment),
        "enquiry_id": _get_enquiry_id(attachment),
        "filename": attachment.filename,
        "file_path": attachment.file_path,
        "reason": reason,
        "uploaded_at": attachment.uploaded_at.strftime("%Y-%m-%d %H:%M"),
    }


def _check_image_integrity(file_path):
    """Try to load an image file to verify it is not corrupted.

    Returns an error message string if corrupted, or None if OK.
    """
    if not Image:
        return None

    try:
        from PIL import ImageFile

        ImageFile.LOAD_TRUNCATED_IMAGES = True

        with Image.open(file_path) as img:
            img.load()
    except Exception as img_error:
        return f"Image corrupted: {str(img_error)}"

    return None


def _check_file_corruption(file_path, attachment):
    """Check whether an existing file is corrupted.

    Returns a corrupted-file record dict, or None if the file is healthy.
    """
    try:
        actual_size = file_path.stat().st_size
    except Exception as e:
        return _build_corrupted_file_record(attachment, f"Cannot read file: {str(e)}")

    if actual_size == 0:
        return _build_corrupted_file_record(attachment, "File is 0 bytes (corrupted)")

    is_image = file_path.suffix.lower() in [".jpg", ".jpeg", ".png"]
    if not is_image:
        return None

    error_msg = _check_image_integrity(file_path)
    if error_msg:
        return _build_corrupted_file_record(attachment, error_msg)

    return None


@login_required
@admin_required()
@require_http_methods(["POST"])
@csrf_protect
def check_missing_images(request):
    """
    Check for missing image files referenced in EnquiryAttachment records.
    Returns a list of missing files with enquiry references.
    """
    try:
        media_root = Path(settings.MEDIA_ROOT)
        missing_files = []
        corrupted_files = []
        total_checked = 0

        attachments = EnquiryAttachment.objects.select_related("enquiry").all()

        for attachment in attachments:
            total_checked += 1
            file_path = media_root / attachment.file_path

            if not file_path.exists():
                missing_files.append(_build_missing_file_record(attachment))
                continue

            corruption = _check_file_corruption(file_path, attachment)
            if corruption:
                corrupted_files.append(corruption)

        missing_files.sort(key=lambda x: x["enquiry_ref"])
        corrupted_files.sort(key=lambda x: x["enquiry_ref"])

        return JsonResponse(
            {
                "success": True,
                "total_checked": total_checked,
                "missing_count": len(missing_files),
                "corrupted_count": len(corrupted_files),
                "missing_files": missing_files,
                "corrupted_files": corrupted_files,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Attachment size update helpers
# ---------------------------------------------------------------------------


def _process_attachment_size(attachment, file_path, stats, dry_run):
    """Check and optionally update a single attachment's file size.

    Mutates *stats* in place.
    """
    try:
        actual_size = file_path.stat().st_size
    except Exception:
        return

    db_size = attachment.file_size or 0
    size_difference = abs(actual_size - db_size)

    if size_difference < 1024:
        stats["files_matched"] += 1
        return

    stats["files_updated"] += 1
    stats["total_size_difference"] += db_size - actual_size

    enquiry_ref = attachment.enquiry.reference if attachment.enquiry else "N/A"

    if len(stats["details"]) < 20:
        stats["details"].append(
            {
                "enquiry_ref": enquiry_ref,
                "filename": attachment.filename,
                "old_size": format_file_size(db_size),
                "new_size": format_file_size(actual_size),
            }
        )

    if dry_run:
        return

    attachment.file_size = actual_size
    attachment.save(update_fields=["file_size"])

    file_logger.log_size_update(
        file_path=attachment.file_path,
        old_size=db_size,
        new_size=actual_size,
        enquiry_ref=enquiry_ref,
    )


@login_required
@admin_required()
@require_http_methods(["POST"])
@csrf_protect
def update_attachment_sizes(request):
    """
    Update EnquiryAttachment file sizes to match actual file sizes on disk.
    Returns JSON with statistics about the update operation.
    """
    try:
        dry_run = request.POST.get("dry_run", "false").lower() == "true"

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            return JsonResponse(
                {"success": False, "error": f"Media directory not found: {media_root}"}
            )

        stats = {
            "total_checked": 0,
            "files_updated": 0,
            "files_missing": 0,
            "files_matched": 0,
            "total_size_difference": 0,
            "details": [],
        }

        attachments = EnquiryAttachment.objects.select_related("enquiry").all()

        for attachment in attachments:
            stats["total_checked"] += 1
            file_path = media_root / attachment.file_path

            if not file_path.exists():
                stats["files_missing"] += 1
                continue

            _process_attachment_size(attachment, file_path, stats, dry_run)

        response = {
            "success": True,
            "total_checked": stats["total_checked"],
            "files_updated": stats["files_updated"],
            "files_matched": stats["files_matched"],
            "files_missing": stats["files_missing"],
            "details": stats["details"],
        }

        if stats["total_size_difference"] > 0:
            response["total_size_reduction"] = format_file_size(
                stats["total_size_difference"]
            )

        return JsonResponse(response)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"

    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0

    return f"{size_bytes:.1f} TB"
