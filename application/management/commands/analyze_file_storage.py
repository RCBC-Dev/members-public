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
Django management command to analyze file storage usage and organization.

This command provides comprehensive analytics about file storage including:
- Storage usage by directory and file type
- Orphaned file detection
- File size distribution analysis
- Organization efficiency metrics
- Cleanup recommendations

Usage:
    python manage.py analyze_file_storage
    python manage.py analyze_file_storage --detailed
    python manage.py analyze_file_storage --find-orphans
    python manage.py analyze_file_storage --export-csv
"""

import os
import csv
import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from application.models import EnquiryAttachment


class Command(BaseCommand):
    help = "Analyze file storage usage and organization"

    def add_arguments(self, parser):
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed analysis including file-by-file breakdown",
        )
        parser.add_argument(
            "--find-orphans",
            action="store_true",
            help="Identify orphaned files not linked to any enquiry",
        )
        parser.add_argument(
            "--export-csv",
            type=str,
            help="Export detailed results to CSV file",
        )
        parser.add_argument(
            "--directory",
            type=str,
            help="Analyze specific directory (default: all media directories)",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("File Storage Analysis Tool"))
        self.stdout.write("=" * 60)

        # Initialize analysis data
        self.analysis_data = {
            "directories": {},
            "file_types": defaultdict(lambda: {"count": 0, "size": 0}),
            "size_distribution": defaultdict(int),
            "orphaned_files": [],
            "total_files": 0,
            "total_size": 0,
            "analysis_date": timezone.now().isoformat(),
        }

        # Get media root
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f"Media directory not found: {media_root}")

        # Determine directories to analyze
        if options["directory"]:
            target_dir = media_root / options["directory"]
            if not target_dir.exists():
                raise CommandError(f"Directory not found: {target_dir}")
            directories = [target_dir]
        else:
            # Analyze main media directories
            directories = [
                media_root / "enquiry_photos",
                media_root / "enquiry_attachments",
                media_root / "django-summernote",
            ]
            directories = [d for d in directories if d.exists()]

        # Perform analysis
        for directory in directories:
            self.analyze_directory(directory)

        # Find orphaned files if requested
        if options["find_orphans"]:
            self.find_orphaned_files()

        # Display results
        self.display_analysis(options["detailed"])

        # Export to CSV if requested
        if options["export_csv"]:
            self.export_to_csv(options["export_csv"])

        self.stdout.write(self.style.SUCCESS("Analysis completed successfully!"))

    def analyze_directory(self, directory):
        """Analyze a specific directory and its subdirectories."""
        self.stdout.write(f"Analyzing: {directory}")

        dir_data = {
            "path": str(directory),
            "total_files": 0,
            "total_size": 0,
            "subdirectories": {},
            "file_types": defaultdict(lambda: {"count": 0, "size": 0}),
            "files": [],
        }

        try:
            for root, dirs, files in os.walk(directory):
                root_path = Path(root)

                for file in files:
                    file_path = root_path / file
                    if file_path.is_file():
                        file_info = self.analyze_file(file_path)

                        # Update directory data
                        dir_data["total_files"] += 1
                        dir_data["total_size"] += file_info["size"]
                        dir_data["files"].append(file_info)

                        # Update file type data
                        ext = file_info["extension"]
                        dir_data["file_types"][ext]["count"] += 1
                        dir_data["file_types"][ext]["size"] += file_info["size"]

                        # Update global data
                        self.analysis_data["total_files"] += 1
                        self.analysis_data["total_size"] += file_info["size"]
                        self.analysis_data["file_types"][ext]["count"] += 1
                        self.analysis_data["file_types"][ext]["size"] += file_info[
                            "size"
                        ]

                        # Update size distribution
                        size_category = self.categorize_file_size(file_info["size"])
                        self.analysis_data["size_distribution"][size_category] += 1

        except PermissionError as e:
            self.stdout.write(
                self.style.WARNING(f"Permission denied accessing {directory}: {e}")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error analyzing {directory}: {e}"))

        self.analysis_data["directories"][str(directory)] = dir_data

    def analyze_file(self, file_path):
        """Analyze a single file and return its information."""
        try:
            stat = file_path.stat()
            return {
                "path": str(file_path),
                "name": file_path.name,
                "extension": file_path.suffix.lower(),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "created": datetime.fromtimestamp(stat.st_ctime),
            }
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Error analyzing file {file_path}: {e}")
            )
            return {
                "path": str(file_path),
                "name": file_path.name,
                "extension": file_path.suffix.lower(),
                "size": 0,
                "modified": None,
                "created": None,
                "error": str(e),
            }

    def categorize_file_size(self, size_bytes):
        """Categorize file size into ranges."""
        if size_bytes < 1024:  # < 1KB
            return "tiny"
        elif size_bytes < 10 * 1024:  # < 10KB
            return "small"
        elif size_bytes < 100 * 1024:  # < 100KB
            return "medium"
        elif size_bytes < 1024 * 1024:  # < 1MB
            return "large"
        elif size_bytes < 10 * 1024 * 1024:  # < 10MB
            return "very_large"
        else:  # >= 10MB
            return "huge"

    def find_orphaned_files(self):
        """Find files that are not linked to any enquiry attachment."""
        self.stdout.write("Searching for orphaned files...")
        self.stdout.write(
            "NOTE: Summernote images are NOT checked as they are embedded in enquiry descriptions"
        )

        # Get all attachment file paths from database
        db_file_paths = set()
        for attachment in EnquiryAttachment.objects.all():
            if attachment.file_path:
                # Normalize path separators
                normalized_path = attachment.file_path.replace("\\", "/")
                db_file_paths.add(normalized_path)

        # Check each file in enquiry directories (NOT summernote)
        media_root = Path(settings.MEDIA_ROOT)
        enquiry_dirs = [
            media_root / "enquiry_photos",
            media_root / "enquiry_attachments",
        ]

        orphaned_count = 0
        orphaned_size = 0

        for directory in enquiry_dirs:
            if not directory.exists():
                continue

            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = Path(root) / file

                    # Get relative path from media root
                    try:
                        relative_path = file_path.relative_to(media_root)
                        normalized_relative = str(relative_path).replace("\\", "/")

                        if normalized_relative not in db_file_paths:
                            file_info = self.analyze_file(file_path)
                            self.analysis_data["orphaned_files"].append(
                                {
                                    "path": str(file_path),
                                    "relative_path": normalized_relative,
                                    "size": file_info["size"],
                                    "modified": file_info["modified"],
                                    "extension": file_info["extension"],
                                }
                            )
                            orphaned_count += 1
                            orphaned_size += file_info["size"]

                    except ValueError:
                        # File is not under media root
                        continue

        self.stdout.write(
            f"Found {orphaned_count} orphaned files ({self.format_size(orphaned_size)})"
        )

    def display_analysis(self, detailed=False):
        """Display the analysis results."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("STORAGE ANALYSIS RESULTS")
        self.stdout.write("=" * 60)

        # Overall statistics
        self.stdout.write(f'Total files: {self.analysis_data["total_files"]:,}')
        self.stdout.write(
            f'Total size: {self.format_size(self.analysis_data["total_size"])}'
        )
        self.stdout.write("")

        # Directory breakdown
        self.stdout.write("DIRECTORY BREAKDOWN")
        self.stdout.write("-" * 40)
        for dir_path, dir_data in self.analysis_data["directories"].items():
            dir_name = Path(dir_path).name
            self.stdout.write(f"{dir_name}:")
            self.stdout.write(f'  Files: {dir_data["total_files"]:,}')
            self.stdout.write(f'  Size: {self.format_size(dir_data["total_size"])}')

            if detailed:
                self.stdout.write("  File types:")
                for ext, data in sorted(dir_data["file_types"].items()):
                    self.stdout.write(
                        f'    {ext or "no extension"}: {data["count"]} files, {self.format_size(data["size"])}'
                    )
            self.stdout.write("")

        # File type summary
        self.stdout.write("FILE TYPE SUMMARY")
        self.stdout.write("-" * 40)
        for ext, data in sorted(
            self.analysis_data["file_types"].items(),
            key=lambda x: x[1]["size"],
            reverse=True,
        ):
            percentage = (data["size"] / self.analysis_data["total_size"]) * 100
            self.stdout.write(
                f'{ext or "no extension"}: {data["count"]} files, {self.format_size(data["size"])} ({percentage:.1f}%)'
            )

        # Size distribution
        self.stdout.write("\nFILE SIZE DISTRIBUTION")
        self.stdout.write("-" * 40)
        size_labels = {
            "tiny": "< 1KB",
            "small": "1KB - 10KB",
            "medium": "10KB - 100KB",
            "large": "100KB - 1MB",
            "very_large": "1MB - 10MB",
            "huge": "> 10MB",
        }
        for category in ["tiny", "small", "medium", "large", "very_large", "huge"]:
            count = self.analysis_data["size_distribution"][category]
            if count > 0:
                percentage = (count / self.analysis_data["total_files"]) * 100
                self.stdout.write(
                    f"{size_labels[category]}: {count} files ({percentage:.1f}%)"
                )

        # Orphaned files summary
        if self.analysis_data["orphaned_files"]:
            orphaned_count = len(self.analysis_data["orphaned_files"])
            orphaned_size = sum(f["size"] for f in self.analysis_data["orphaned_files"])
            self.stdout.write("\nORPHANED FILES")
            self.stdout.write("-" * 40)
            self.stdout.write(f"Count: {orphaned_count}")
            self.stdout.write(f"Total size: {self.format_size(orphaned_size)}")

            if detailed and orphaned_count > 0:
                self.stdout.write("Files:")
                for orphan in self.analysis_data["orphaned_files"][
                    :20
                ]:  # Show first 20
                    self.stdout.write(
                        f'  {orphan["relative_path"]} ({self.format_size(orphan["size"])})'
                    )
                if orphaned_count > 20:
                    self.stdout.write(f"  ... and {orphaned_count - 20} more")

    def export_to_csv(self, filename):
        """Export analysis results to CSV file."""
        self.stdout.write(f"Exporting results to {filename}...")

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(
                [
                    "Directory",
                    "File Path",
                    "File Name",
                    "Extension",
                    "Size (bytes)",
                    "Size (formatted)",
                    "Modified",
                    "Is Orphaned",
                ]
            )

            # Write file data
            for dir_path, dir_data in self.analysis_data["directories"].items():
                dir_name = Path(dir_path).name
                orphaned_paths = {
                    f["path"] for f in self.analysis_data["orphaned_files"]
                }

                for file_info in dir_data["files"]:
                    is_orphaned = file_info["path"] in orphaned_paths
                    writer.writerow(
                        [
                            dir_name,
                            file_info["path"],
                            file_info["name"],
                            file_info["extension"],
                            file_info["size"],
                            self.format_size(file_info["size"]),
                            (
                                file_info["modified"].isoformat()
                                if file_info["modified"]
                                else ""
                            ),
                            "Yes" if is_orphaned else "No",
                        ]
                    )

        self.stdout.write(f"Results exported to {filename}")

    def format_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"

        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0

        return f"{size_bytes:.1f} TB"
