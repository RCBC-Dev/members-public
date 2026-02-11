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


@login_required
@admin_required()
@require_http_methods(["GET", "POST"])
def optimize_enquiry_images_stream(request):
    """
    Stream real-time progress for enquiry image optimization.
    """
    # Support both GET and POST for EventSource compatibility
    if request.method == "GET":
        quality = int(request.GET.get("quality", 85))
        dry_run = request.GET.get("dry_run", "false").lower() == "true"
        min_size_mb = float(request.GET.get("min_size_mb", 1.0))
        max_dimension = int(request.GET.get("max_dimension", 1920))
    else:
        quality = int(request.POST.get("quality", 85))
        dry_run = request.POST.get("dry_run", "false").lower() == "true"
        min_size_mb = float(request.POST.get("min_size_mb", 1.0))
        max_dimension = int(request.POST.get("max_dimension", 1920))

    def generate_progress():
        """Generator function for streaming progress updates."""
        try:
            print(
                f"DEBUG: Starting optimization with quality={quality}, dry_run={dry_run}, min_size_mb={min_size_mb}"
            )

            if Image is None:
                yield f"data: {json.dumps({'error': 'PIL (Pillow) is not installed. Please install it with: pip install Pillow'})}\n\n"
                return

            enquiry_photos_dir = Path(settings.MEDIA_ROOT) / "enquiry_photos"

            if not enquiry_photos_dir.exists():
                yield f"data: {json.dumps({'error': 'No image directory found (enquiry_photos)'})}\n\n"
                return

            existing_dirs = [enquiry_photos_dir]

            # Count total files and filter for optimization candidates
            total_files = 0
            image_files = []
            skipped_files = 0
            min_size_bytes = min_size_mb * 1024 * 1024

            yield f"data: {json.dumps({'status': 'scanning', 'message': 'Scanning enquiry images for optimization candidates...'})}\n\n"

            # Scan all image directories
            for image_dir in existing_dirs:
                for root, dirs, files in os.walk(image_dir):
                    for filename in files:
                        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                            file_path = Path(root) / filename
                            try:
                                file_size = file_path.stat().st_size

                                # Only process files larger than threshold
                                if file_size > min_size_bytes:
                                    # Advanced analysis for optimization candidates
                                    needs_optimization = True
                                    skip_reason = ""

                                    try:
                                        with Image.open(file_path) as img:
                                            width, height = img.size
                                            pixels = width * height
                                            bytes_per_pixel = (
                                                file_size / pixels if pixels > 0 else 0
                                            )

                                            # Different logic for different file types
                                            if filename.lower().endswith(".png"):
                                                # PNG files: Focus on large files and dimensions
                                                if (
                                                    width > max_dimension
                                                    or height > max_dimension
                                                ):
                                                    # Large dimensions always need optimization
                                                    needs_optimization = True
                                                    skip_reason = f"Large PNG dimensions ({width}x{height}) need resizing/conversion"
                                                elif (
                                                    file_size > 1024 * 1024
                                                ):  # > 1MB PNG
                                                    # Large PNG files should be optimized (possibly converted to JPEG)
                                                    needs_optimization = True
                                                    skip_reason = f"Large PNG file ({format_file_size(file_size)}) needs optimization"
                                                elif (
                                                    bytes_per_pixel < 0.5
                                                    and file_size < 500 * 1024
                                                ):  # Very efficient and small
                                                    needs_optimization = False
                                                    skip_reason = "PNG already very efficient and small"
                                                else:
                                                    # Default to optimizing PNGs over threshold
                                                    needs_optimization = True
                                                    skip_reason = "PNG will be analyzed for optimization"

                                            elif filename.lower().endswith(
                                                (".jpg", ".jpeg")
                                            ):
                                                # JPEG files: Prioritize dimension reduction over compression analysis
                                                if (
                                                    width > max_dimension
                                                    or height > max_dimension
                                                ):
                                                    # Large dimensions always need optimization (resize)
                                                    needs_optimization = True
                                                    skip_reason = f"Large dimensions ({width}x{height}) need resizing"
                                                elif (
                                                    file_size > 2 * 1024 * 1024
                                                ):  # > 2MB
                                                    # Large files always need optimization regardless of compression
                                                    needs_optimization = True
                                                    skip_reason = f"Large file size ({format_file_size(file_size)}) needs compression"
                                                elif (
                                                    bytes_per_pixel < 0.15
                                                    and file_size < 1024 * 1024
                                                ):  # Very well compressed and small
                                                    needs_optimization = False
                                                    skip_reason = "JPEG already very well-compressed and reasonably sized"
                                                else:
                                                    # Default to optimizing if we're not sure
                                                    needs_optimization = True
                                                    skip_reason = (
                                                        "Will attempt optimization"
                                                    )

                                            # Log analysis for debugging
                                            if not needs_optimization:
                                                print(
                                                    f"DEBUG: SKIPPING {filename}: {skip_reason} ({width}x{height}, {format_file_size(file_size)}, {bytes_per_pixel:.2f} bytes/pixel)"
                                                )
                                            else:
                                                print(
                                                    f"DEBUG: WILL OPTIMIZE {filename}: {skip_reason} ({width}x{height}, {format_file_size(file_size)}, {bytes_per_pixel:.2f} bytes/pixel)"
                                                )

                                    except Exception as e:
                                        # If we can't analyze, assume it needs optimization
                                        print(f"DEBUG: Cannot analyze {filename}: {e}")
                                        needs_optimization = True

                                    if needs_optimization:
                                        image_files.append(file_path)
                                        total_files += 1
                                    else:
                                        skipped_files += 1
                                else:
                                    skipped_files += 1
                            except OSError:
                                continue

            yield f"data: {json.dumps({'status': 'starting', 'total_files': total_files, 'skipped_files': skipped_files, 'min_size_mb': min_size_mb, 'dry_run': dry_run})}\n\n"

            if total_files == 0:
                if skipped_files > 0:
                    yield f"data: {json.dumps({'status': 'complete', 'message': f'No optimization needed! Found {skipped_files} images, but all are either smaller than {min_size_mb}MB or already well-compressed.'})}\n\n"
                else:
                    yield f"data: {json.dumps({'status': 'complete', 'message': 'No image files found to optimize'})}\n\n"
                return

            results = {
                "processed": 0,
                "errors": 0,
                "total_size_before": 0,
                "total_size_after": 0,
                "error_files": [],
            }

            # Process each image file
            for i, file_path in enumerate(image_files, 1):
                try:
                    filename = file_path.name
                    progress_percent = round((i / total_files) * 100, 1)
                    yield f"data: {json.dumps({'status': 'processing', 'current_file': filename, 'progress': i, 'total': total_files, 'percent': progress_percent})}\n\n"

                    # Get original size
                    original_size = file_path.stat().st_size
                    results["total_size_before"] += original_size

                    if not dry_run:
                        # Optimize image with advanced processing
                        with Image.open(file_path) as img:
                            original_width, original_height = img.size

                            # Resize if image is too large
                            resized = False
                            old_dimensions = None
                            new_dimensions = None
                            if (
                                original_width > max_dimension
                                or original_height > max_dimension
                            ):
                                # Calculate new dimensions maintaining aspect ratio
                                if original_width > original_height:
                                    new_width = max_dimension
                                    new_height = int(
                                        (original_height * max_dimension)
                                        / original_width
                                    )
                                else:
                                    new_height = max_dimension
                                    new_width = int(
                                        (original_width * max_dimension)
                                        / original_height
                                    )

                                old_dimensions = f"{original_width}x{original_height}"
                                new_dimensions = f"{new_width}x{new_height}"
                                resized = True

                                img = img.resize(
                                    (new_width, new_height), Image.Resampling.LANCZOS
                                )
                                yield f"data: {json.dumps({'status': 'file_resized', 'filename': filename, 'old_size': old_dimensions, 'new_size': new_dimensions})}\n\n"

                            # Handle different file types
                            is_png = filename.lower().endswith(".png")

                            if is_png:
                                # For PNG files, try converting to JPEG if it's photographic
                                # Check if PNG has transparency
                                has_transparency = (
                                    img.mode in ("RGBA", "LA")
                                    or "transparency" in img.info
                                )

                                if (
                                    not has_transparency and original_size > 1024 * 1024
                                ):  # > 1MB PNG without transparency
                                    # Convert to JPEG for better compression
                                    # BUT: Find attachment FIRST before changing filename
                                    old_relative_path = str(
                                        file_path.relative_to(settings.MEDIA_ROOT)
                                    ).replace("\\", "/")
                                    attachment_to_update = (
                                        EnquiryAttachment.objects.filter(
                                            file_path=old_relative_path
                                        ).first()
                                    )

                                    if img.mode in ("RGBA", "LA", "P"):
                                        img = img.convert("RGB")

                                    # Save as JPEG with new extension
                                    new_path = file_path.with_suffix(".jpg")
                                    img.save(
                                        new_path, "JPEG", optimize=True, quality=quality
                                    )

                                    # Update database BEFORE deleting old file
                                    if attachment_to_update:
                                        new_relative_path = str(
                                            new_path.relative_to(settings.MEDIA_ROOT)
                                        ).replace("\\", "/")
                                        new_filename = new_path.name

                                        attachment_to_update.file_path = (
                                            new_relative_path
                                        )
                                        attachment_to_update.filename = new_filename
                                        attachment_to_update.save(
                                            update_fields=["file_path", "filename"]
                                        )

                                        # Log the conversion (don't let logging errors stop deletion)
                                        try:
                                            file_logger.log_move(
                                                old_path=old_relative_path,
                                                new_path=new_relative_path,
                                                reason="PNG→JPEG conversion for compression",
                                            )
                                        except Exception:
                                            pass  # Don't let logging errors prevent file cleanup

                                        # NOW safe to remove original PNG
                                        file_path.unlink()
                                        file_path = new_path

                                        yield f"data: {json.dumps({'status': 'file_converted', 'filename': filename, 'new_format': 'JPEG'})}\n\n"
                                    else:
                                        # No database record found - still delete PNG to avoid orphans
                                        file_path.unlink()
                                        file_path = new_path
                                        yield f"data: {json.dumps({'status': 'file_converted', 'filename': filename, 'new_format': 'JPEG', 'warning': 'No database record found'})}\n\n"
                                else:
                                    # Keep as PNG but optimize
                                    img.save(file_path, "PNG", optimize=True)
                            else:
                                # JPEG optimization
                                if img.mode in ("RGBA", "LA"):
                                    background = Image.new(
                                        "RGB", img.size, (255, 255, 255)
                                    )
                                    background.paste(
                                        img,
                                        mask=(
                                            img.split()[-1]
                                            if img.mode == "RGBA"
                                            else None
                                        ),
                                    )
                                    img = background

                                # Save with compression
                                img.save(
                                    file_path, "JPEG", optimize=True, quality=quality
                                )

                        # Get new size
                        new_size = file_path.stat().st_size

                        # Update database file size and log the operation
                        relative_path = str(
                            file_path.relative_to(settings.MEDIA_ROOT)
                        ).replace("\\", "/")
                        attachment = EnquiryAttachment.objects.filter(
                            file_path=relative_path
                        ).first()

                        if attachment:
                            enquiry_ref = (
                                attachment.enquiry.reference
                                if attachment.enquiry
                                else None
                            )

                            # Log resize if it occurred
                            if resized:
                                file_logger.log_resize(
                                    file_path=relative_path,
                                    old_dimensions=old_dimensions,
                                    new_dimensions=new_dimensions,
                                    enquiry_ref=enquiry_ref,
                                )

                            # Log compression
                            file_logger.log_compression(
                                file_path=relative_path,
                                original_size=format_file_size(original_size),
                                new_size=format_file_size(new_size),
                                savings_percent=(
                                    round(
                                        (original_size - new_size)
                                        / original_size
                                        * 100,
                                        1,
                                    )
                                    if original_size > 0
                                    else 0
                                ),
                                enquiry_ref=enquiry_ref,
                            )

                            # Update database if size changed
                            if attachment.file_size != new_size:
                                old_db_size = attachment.file_size
                                attachment.file_size = new_size
                                attachment.save(update_fields=["file_size"])

                                # Log size update
                                file_logger.log_size_update(
                                    file_path=relative_path,
                                    old_size=old_db_size,
                                    new_size=new_size,
                                    enquiry_ref=enquiry_ref,
                                )
                    else:
                        # For dry run, estimate compression
                        new_size = int(original_size * (quality / 100))

                    results["total_size_after"] += new_size
                    results["processed"] += 1

                    # Calculate savings for this file
                    file_savings = original_size - new_size
                    file_savings_percent = (
                        (file_savings / original_size * 100) if original_size > 0 else 0
                    )

                    yield f"data: {json.dumps({'status': 'file_complete', 'filename': filename, 'original_size': original_size, 'new_size': new_size, 'savings': file_savings, 'savings_percent': round(file_savings_percent, 1), 'original_formatted': format_file_size(original_size), 'new_formatted': format_file_size(new_size), 'savings_formatted': format_file_size(file_savings)})}\n\n"

                except Exception as e:
                    results["errors"] += 1
                    results["error_files"].append(
                        {"filename": file_path.name, "error": str(e)}
                    )

                    # Log error
                    relative_path = str(
                        file_path.relative_to(settings.MEDIA_ROOT)
                    ).replace("\\", "/")
                    file_logger.log_error(
                        operation="COMPRESS", file_path=relative_path, error_msg=str(e)
                    )

                    yield f"data: {json.dumps({'status': 'file_error', 'filename': file_path.name, 'error': str(e)})}\n\n"

            # Calculate final results
            savings = results["total_size_before"] - results["total_size_after"]
            savings_percent = (
                (savings / results["total_size_before"] * 100)
                if results["total_size_before"] > 0
                else 0
            )

            final_results = {
                "status": "complete",
                "processed": results["processed"],
                "errors": results["errors"],
                "total_files": total_files,
                "savings_bytes": savings,
                "savings_percent": round(savings_percent, 1),
                "total_size_before": results["total_size_before"],
                "total_size_after": results["total_size_after"],
                "total_size_before_formatted": format_file_size(
                    results["total_size_before"]
                ),
                "total_size_after_formatted": format_file_size(
                    results["total_size_after"]
                ),
                "savings_formatted": format_file_size(savings),
                "error_files": results["error_files"],
                "dry_run": dry_run,
            }

            yield f"data: {json.dumps(final_results)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    # Return streaming response
    from django.http import StreamingHttpResponse

    response = StreamingHttpResponse(
        generate_progress(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disable nginx buffering
    # Note: Connection header removed for Django dev server compatibility
    return response


@login_required
@admin_required()
def file_browser(request):
    """
    Browse files in the media directory with DataTables interface.
    """
    directory = request.GET.get("dir", "enquiry_photos")

    # Security check - only allow specific directories
    allowed_dirs = ["enquiry_photos", "enquiry_attachments"]
    if directory not in allowed_dirs:
        directory = "enquiry_photos"

    # For debugging, let's also get the files data directly
    media_root = Path(settings.MEDIA_ROOT)
    target_dir = media_root / directory

    files = []
    if target_dir.exists():
        # Get all files in directory
        for root, dirs, filenames in os.walk(target_dir):
            for filename in filenames:
                file_path = Path(root) / filename
                try:
                    stat = file_path.stat()
                    relative_path = file_path.relative_to(media_root)

                    # Check if file is linked to an enquiry and get display name
                    normalized_path = str(relative_path).replace("\\", "/")
                    attachment = EnquiryAttachment.objects.filter(
                        file_path=normalized_path
                    ).first()

                    is_linked = attachment is not None
                    display_name = filename  # Default to filename
                    enquiry_ref = None
                    enquiry_id = None

                    if attachment:
                        # Use the original filename (stored in 'filename' field)
                        display_name = attachment.filename

                        # Get enquiry reference and ID for linking
                        if attachment.enquiry:
                            enquiry_ref = attachment.enquiry.reference
                            enquiry_id = attachment.enquiry.pk

                    files.append(
                        {
                            "name": filename,
                            "display_name": display_name,
                            "path": str(relative_path),
                            "size": stat.st_size,
                            "size_formatted": format_file_size(stat.st_size),
                            "modified": datetime.fromtimestamp(stat.st_mtime),
                            "is_linked": is_linked,
                            "extension": file_path.suffix.lower(),
                            "enquiry_ref": enquiry_ref,
                            "enquiry_id": enquiry_id,
                        }
                    )
                except OSError:
                    continue

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
def file_browser_data(request):
    """
    DataTables-compatible API endpoint for file browser data.
    """
    directory = request.GET.get("directory", "enquiry_photos")

    # Security check - only allow specific directories
    allowed_dirs = ["enquiry_photos", "enquiry_attachments"]
    if directory not in allowed_dirs:
        directory = "enquiry_photos"

    media_root = Path(settings.MEDIA_ROOT)
    target_dir = media_root / directory

    files = []
    if target_dir.exists():
        # Get all files in directory
        for root, dirs, filenames in os.walk(target_dir):
            for filename in filenames:
                file_path = Path(root) / filename
                try:
                    stat = file_path.stat()
                    relative_path = file_path.relative_to(media_root)

                    # Check if file is linked to an enquiry and get display name
                    normalized_path = str(relative_path).replace("\\", "/")
                    attachment = EnquiryAttachment.objects.filter(
                        file_path=normalized_path
                    ).first()

                    is_linked = attachment is not None
                    display_name = filename  # Default to filename
                    enquiry_ref = None
                    enquiry_id = None

                    if attachment:
                        # Use the original filename (stored in 'filename' field)
                        display_name = attachment.filename

                        # Get enquiry reference and ID for linking
                        if attachment.enquiry:
                            enquiry_ref = attachment.enquiry.reference
                            enquiry_id = attachment.enquiry.pk

                    files.append(
                        {
                            "name": filename,
                            "display_name": display_name,
                            "path": str(relative_path),
                            "size": stat.st_size,
                            "size_formatted": format_file_size(stat.st_size),
                            "modified": datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                            "is_linked": is_linked,
                            "extension": file_path.suffix.lower(),
                            "enquiry_ref": enquiry_ref,
                            "enquiry_id": enquiry_id,
                        }
                    )
                except OSError:
                    continue

    # Return DataTables-compatible JSON
    return JsonResponse({"data": files})


@login_required
@admin_required()
def storage_analytics_api(request):
    """
    API endpoint for storage analytics data (for charts and graphs).
    """
    try:
        # Get storage data by date
        media_root = Path(settings.MEDIA_ROOT)

        # Analyze files by date
        date_stats = defaultdict(lambda: {"files": 0, "size": 0})
        file_type_stats = defaultdict(lambda: {"files": 0, "size": 0})

        for directory_name in ["enquiry_photos", "enquiry_attachments"]:
            directory_path = media_root / directory_name
            if directory_path.exists():
                for root, dirs, files in os.walk(directory_path):
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            stat = file_path.stat()
                            file_date = datetime.fromtimestamp(stat.st_mtime).date()
                            file_ext = file_path.suffix.lower()

                            date_stats[str(file_date)]["files"] += 1
                            date_stats[str(file_date)]["size"] += stat.st_size

                            file_type_stats[file_ext]["files"] += 1
                            file_type_stats[file_ext]["size"] += stat.st_size

                        except OSError:
                            continue

        # Convert to lists for JSON serialization
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

        # Check all attachments
        attachments = EnquiryAttachment.objects.select_related("enquiry").all()

        for attachment in attachments:
            total_checked += 1
            file_path = media_root / attachment.file_path

            # Check if file exists
            if not file_path.exists():
                missing_files.append(
                    {
                        "enquiry_ref": (
                            attachment.enquiry.reference
                            if attachment.enquiry
                            else "N/A"
                        ),
                        "enquiry_id": (
                            attachment.enquiry.id if attachment.enquiry else None
                        ),
                        "filename": attachment.filename,
                        "file_path": attachment.file_path,
                        "uploaded_at": attachment.uploaded_at.strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        "file_size": (
                            format_file_size(attachment.file_size)
                            if attachment.file_size
                            else "Unknown"
                        ),
                    }
                )
            else:
                # File exists - check if it's corrupted (0 bytes or can't be read)
                try:
                    actual_size = file_path.stat().st_size
                    if actual_size == 0:
                        corrupted_files.append(
                            {
                                "enquiry_ref": (
                                    attachment.enquiry.reference
                                    if attachment.enquiry
                                    else "N/A"
                                ),
                                "enquiry_id": (
                                    attachment.enquiry.id
                                    if attachment.enquiry
                                    else None
                                ),
                                "filename": attachment.filename,
                                "file_path": attachment.file_path,
                                "reason": "File is 0 bytes (corrupted)",
                                "uploaded_at": attachment.uploaded_at.strftime(
                                    "%Y-%m-%d %H:%M"
                                ),
                            }
                        )
                    elif file_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                        # Try to open image files to verify they're not corrupted
                        # Use lenient loading like browsers do - truncated images are OK if displayable
                        if Image:
                            try:
                                from PIL import ImageFile

                                ImageFile.LOAD_TRUNCATED_IMAGES = True

                                with Image.open(file_path) as img:
                                    # Try to load the image (not just verify)
                                    # This matches browser behavior - if it can be displayed, it's not corrupted
                                    img.load()
                            except Exception as img_error:
                                corrupted_files.append(
                                    {
                                        "enquiry_ref": (
                                            attachment.enquiry.reference
                                            if attachment.enquiry
                                            else "N/A"
                                        ),
                                        "enquiry_id": (
                                            attachment.enquiry.id
                                            if attachment.enquiry
                                            else None
                                        ),
                                        "filename": attachment.filename,
                                        "file_path": attachment.file_path,
                                        "reason": f"Image corrupted: {str(img_error)}",
                                        "uploaded_at": attachment.uploaded_at.strftime(
                                            "%Y-%m-%d %H:%M"
                                        ),
                                    }
                                )
                except Exception as e:
                    corrupted_files.append(
                        {
                            "enquiry_ref": (
                                attachment.enquiry.reference
                                if attachment.enquiry
                                else "N/A"
                            ),
                            "enquiry_id": (
                                attachment.enquiry.id if attachment.enquiry else None
                            ),
                            "filename": attachment.filename,
                            "file_path": attachment.file_path,
                            "reason": f"Cannot read file: {str(e)}",
                            "uploaded_at": attachment.uploaded_at.strftime(
                                "%Y-%m-%d %H:%M"
                            ),
                        }
                    )

        # Sort both lists by enquiry reference
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

        # Statistics
        stats = {
            "total_checked": 0,
            "files_updated": 0,
            "files_missing": 0,
            "files_matched": 0,
            "total_size_difference": 0,
            "details": [],
        }

        # Get all attachments
        attachments = EnquiryAttachment.objects.select_related("enquiry").all()

        for attachment in attachments:
            stats["total_checked"] += 1
            file_path = media_root / attachment.file_path

            # Check if file exists
            if not file_path.exists():
                stats["files_missing"] += 1
                continue

            # Get actual file size
            try:
                actual_size = file_path.stat().st_size
                db_size = attachment.file_size or 0
                size_difference = abs(actual_size - db_size)

                # Check if sizes match (within 1KB tolerance)
                if size_difference < 1024:
                    stats["files_matched"] += 1
                    continue

                # Sizes differ - update needed
                stats["files_updated"] += 1
                stats["total_size_difference"] += db_size - actual_size

                enquiry_ref = (
                    attachment.enquiry.reference if attachment.enquiry else "N/A"
                )

                # Store detail for first 20 updates
                if len(stats["details"]) < 20:
                    stats["details"].append(
                        {
                            "enquiry_ref": enquiry_ref,
                            "filename": attachment.filename,
                            "old_size": format_file_size(db_size),
                            "new_size": format_file_size(actual_size),
                        }
                    )

                # Update database if not dry run
                if not dry_run:
                    attachment.file_size = actual_size
                    attachment.save(update_fields=["file_size"])

                    # Log the update
                    file_logger.log_size_update(
                        file_path=attachment.file_path,
                        old_size=db_size,
                        new_size=actual_size,
                        enquiry_ref=enquiry_ref,
                    )

            except Exception as e:
                # Skip files with errors
                continue

        # Build response
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
