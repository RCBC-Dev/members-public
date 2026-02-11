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
Django management command to analyze Summernote image usage in enquiry descriptions.

This command scans all enquiry descriptions to identify which Summernote images
are actually being used and which ones might be orphaned.

Usage:
    python manage.py analyze_summernote_usage
    python manage.py analyze_summernote_usage --find-unused
    python manage.py analyze_summernote_usage --export-csv results.csv
"""

import os
import re
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from application.models import Enquiry


class Command(BaseCommand):
    help = "Analyze Summernote image usage in enquiry descriptions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--find-unused",
            action="store_true",
            help="Find Summernote images that are not referenced in any enquiry",
        )
        parser.add_argument(
            "--export-csv",
            type=str,
            help="Export results to CSV file",
        )
        parser.add_argument(
            "--older-than",
            type=int,
            help="Only consider files older than N days for unused detection",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("Summernote Image Usage Analysis"))
        self.stdout.write("=" * 60)

        # Initialize tracking
        self.analysis_data = {
            "total_summernote_files": 0,
            "total_summernote_size": 0,
            "referenced_files": set(),
            "unreferenced_files": [],
            "enquiries_with_images": 0,
            "analysis_date": timezone.now().isoformat(),
        }

        # Get Summernote directory
        summernote_dir = Path(settings.MEDIA_ROOT) / "django-summernote"
        if not summernote_dir.exists():
            self.stdout.write(self.style.WARNING("No Summernote directory found"))
            return

        # Scan all Summernote files
        self.scan_summernote_files(summernote_dir)

        # Scan all enquiry descriptions for image references
        self.scan_enquiry_descriptions()

        # Find unused files if requested
        if options["find_unused"]:
            self.find_unused_files(summernote_dir, options.get("older_than"))

        # Display results
        self.display_analysis()

        # Export to CSV if requested
        if options["export_csv"]:
            self.export_to_csv(options["export_csv"])

        self.stdout.write(self.style.SUCCESS("Analysis completed successfully!"))

    def scan_summernote_files(self, summernote_dir):
        """Scan all files in the Summernote directory."""
        self.stdout.write("Scanning Summernote files...")

        for root, dirs, files in os.walk(summernote_dir):
            for file in files:
                file_path = Path(root) / file
                try:
                    file_size = file_path.stat().st_size
                    self.analysis_data["total_summernote_files"] += 1
                    self.analysis_data["total_summernote_size"] += file_size
                except OSError:
                    continue

        self.stdout.write(
            f'Found {self.analysis_data["total_summernote_files"]} Summernote files'
        )

    def scan_enquiry_descriptions(self):
        """Scan all enquiry descriptions for Summernote image references."""
        self.stdout.write("Scanning enquiry descriptions for image references...")

        # Pattern to match Summernote image URLs
        # Matches: /media/django-summernote/2024-01-01/image.jpg
        summernote_pattern = re.compile(
            r'/media/django-summernote/[^"\s]+\.(jpg|jpeg|png|gif|webp)', re.IGNORECASE
        )

        enquiries_with_images = 0

        for enquiry in Enquiry.objects.all():
            description = enquiry.description or ""

            # Find all Summernote image references in this enquiry
            matches = summernote_pattern.findall(description)

            if matches:
                enquiries_with_images += 1

                # Extract file paths from the full URLs
                for match in summernote_pattern.finditer(description):
                    url = match.group(0)
                    # Remove /media/ prefix to get relative path
                    if url.startswith("/media/"):
                        relative_path = url[7:]  # Remove '/media/'
                        # URL decode in case of encoded characters
                        relative_path = unquote(relative_path)
                        self.analysis_data["referenced_files"].add(relative_path)

        self.analysis_data["enquiries_with_images"] = enquiries_with_images
        self.stdout.write(
            f'Found {len(self.analysis_data["referenced_files"])} referenced images'
        )
        self.stdout.write(f"Found {enquiries_with_images} enquiries with images")

    def find_unused_files(self, summernote_dir, older_than_days=None):
        """Find Summernote files that are not referenced in any enquiry."""
        self.stdout.write("Finding unused Summernote files...")

        media_root = Path(settings.MEDIA_ROOT)
        cutoff_date = None

        if older_than_days:
            cutoff_date = timezone.now() - timezone.timedelta(days=older_than_days)
            self.stdout.write(f"Only considering files older than {cutoff_date.date()}")

        for root, dirs, files in os.walk(summernote_dir):
            for file in files:
                file_path = Path(root) / file

                try:
                    # Get relative path from media root
                    relative_path = file_path.relative_to(media_root)
                    normalized_relative = str(relative_path).replace("\\", "/")

                    # Check if file is referenced in any enquiry
                    if (
                        normalized_relative
                        not in self.analysis_data["referenced_files"]
                    ):
                        # Check age filter if specified
                        if cutoff_date:
                            file_mtime = datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            )
                            if timezone.make_aware(file_mtime) > cutoff_date:
                                continue

                        file_info = {
                            "path": str(file_path),
                            "relative_path": normalized_relative,
                            "size": file_path.stat().st_size,
                            "modified": datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ),
                            "extension": file_path.suffix.lower(),
                        }
                        self.analysis_data["unreferenced_files"].append(file_info)

                except (ValueError, OSError) as e:
                    self.stdout.write(f"Error processing {file_path}: {e}")

        unreferenced_count = len(self.analysis_data["unreferenced_files"])
        unreferenced_size = sum(
            f["size"] for f in self.analysis_data["unreferenced_files"]
        )

        self.stdout.write(
            f"Found {unreferenced_count} unreferenced files ({self.format_size(unreferenced_size)})"
        )

    def display_analysis(self):
        """Display the analysis results."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SUMMERNOTE USAGE ANALYSIS")
        self.stdout.write("=" * 60)

        # Overall statistics
        self.stdout.write(
            f'Total Summernote files: {self.analysis_data["total_summernote_files"]:,}'
        )
        self.stdout.write(
            f'Total Summernote size: {self.format_size(self.analysis_data["total_summernote_size"])}'
        )
        self.stdout.write(
            f'Referenced images: {len(self.analysis_data["referenced_files"])}'
        )
        self.stdout.write(
            f'Enquiries with images: {self.analysis_data["enquiries_with_images"]}'
        )

        if self.analysis_data["unreferenced_files"]:
            unreferenced_count = len(self.analysis_data["unreferenced_files"])
            unreferenced_size = sum(
                f["size"] for f in self.analysis_data["unreferenced_files"]
            )

            self.stdout.write("\nUNREFERENCED FILES")
            self.stdout.write("-" * 40)
            self.stdout.write(f"Count: {unreferenced_count}")
            self.stdout.write(f"Total size: {self.format_size(unreferenced_size)}")

            # Show some examples
            if unreferenced_count > 0:
                self.stdout.write("\nExamples (first 10):")
                for file_info in self.analysis_data["unreferenced_files"][:10]:
                    age_days = (datetime.now() - file_info["modified"]).days
                    self.stdout.write(
                        f'  {file_info["relative_path"]} '
                        f'({self.format_size(file_info["size"])}, '
                        f"{age_days} days old)"
                    )
                if unreferenced_count > 10:
                    self.stdout.write(f"  ... and {unreferenced_count - 10} more")

        # Usage statistics
        if self.analysis_data["total_summernote_files"] > 0:
            referenced_percentage = (
                len(self.analysis_data["referenced_files"])
                / self.analysis_data["total_summernote_files"]
            ) * 100
            self.stdout.write(
                f"\nUsage rate: {referenced_percentage:.1f}% of files are referenced"
            )

    def export_to_csv(self, filename):
        """Export analysis results to CSV file."""
        self.stdout.write(f"Exporting results to {filename}...")

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(
                ["File Path", "Size (bytes)", "Size (formatted)", "Modified", "Status"]
            )

            # Write referenced files
            for relative_path in sorted(self.analysis_data["referenced_files"]):
                writer.writerow([relative_path, "", "", "", "Referenced"])

            # Write unreferenced files
            for file_info in self.analysis_data["unreferenced_files"]:
                writer.writerow(
                    [
                        file_info["relative_path"],
                        file_info["size"],
                        self.format_size(file_info["size"]),
                        (
                            file_info["modified"].isoformat()
                            if file_info["modified"]
                            else ""
                        ),
                        "Unreferenced",
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
