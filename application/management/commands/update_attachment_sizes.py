"""
Django management command to update file sizes in database to match actual file sizes on disk.

This command is useful after image compression operations where the database
file_size field still shows the original size instead of the compressed size.

Usage:
    python manage.py update_attachment_sizes
    python manage.py update_attachment_sizes --dry-run
    python manage.py update_attachment_sizes --verbose
"""

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Q

from application.models import EnquiryAttachment
from application.file_logger import file_logger


class Command(BaseCommand):
    help = 'Update EnquiryAttachment file sizes to match actual file sizes on disk'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each file',
        )
        parser.add_argument(
            '--min-difference',
            type=int,
            default=1024,
            help='Minimum size difference in bytes to update (default: 1024 bytes)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        min_difference = options['min_difference']

        self.stdout.write(
            self.style.HTTP_INFO('Attachment File Size Update Tool')
        )
        self.stdout.write('=' * 60)

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )

        # Get media root
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f'Media directory not found: {media_root}')

        # Statistics
        stats = {
            'total_checked': 0,
            'files_updated': 0,
            'files_missing': 0,
            'files_matched': 0,
            'total_size_difference': 0,
        }

        # Get all attachments
        self.stdout.write('Checking all attachment file sizes...\n')
        attachments = EnquiryAttachment.objects.select_related('enquiry').all()

        for attachment in attachments:
            stats['total_checked'] += 1
            file_path = media_root / attachment.file_path

            # Check if file exists
            if not file_path.exists():
                stats['files_missing'] += 1
                if verbose:
                    self.stdout.write(
                        self.style.WARNING(f'  Missing: {attachment.file_path}')
                    )
                continue

            # Get actual file size
            try:
                actual_size = file_path.stat().st_size
                db_size = attachment.file_size or 0
                size_difference = abs(actual_size - db_size)

                # Check if sizes match (within tolerance)
                if size_difference < min_difference:
                    stats['files_matched'] += 1
                    if verbose:
                        self.stdout.write(
                            self.style.SUCCESS(f'  OK: {attachment.file_path} ({self.format_size(actual_size)})')
                        )
                    continue

                # Sizes differ - update needed
                stats['files_updated'] += 1
                stats['total_size_difference'] += (db_size - actual_size)

                enquiry_ref = attachment.enquiry.reference if attachment.enquiry else 'N/A'

                if verbose or not dry_run:
                    size_change = self.format_size(db_size - actual_size)
                    sign = '+' if db_size > actual_size else '-'
                    self.stdout.write(
                        f'  Update: {attachment.file_path}'
                    )
                    self.stdout.write(
                        f'    Enquiry: {enquiry_ref}'
                    )
                    self.stdout.write(
                        f'    DB size: {self.format_size(db_size)} → Actual size: {self.format_size(actual_size)}'
                    )
                    self.stdout.write(
                        f'    Difference: {sign}{size_change}'
                    )

                # Update database
                if not dry_run:
                    attachment.file_size = actual_size
                    attachment.save(update_fields=['file_size'])

                    # Log the update
                    file_logger.log_size_update(
                        file_path=attachment.file_path,
                        old_size=db_size,
                        new_size=actual_size,
                        enquiry_ref=enquiry_ref
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  Error checking {attachment.file_path}: {e}')
                )
                continue

        # Display summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Total attachments checked: {stats["total_checked"]}')
        self.stdout.write(f'Files with matching sizes: {stats["files_matched"]}')
        self.stdout.write(f'Files updated: {stats["files_updated"]}')
        self.stdout.write(f'Missing files: {stats["files_missing"]}')

        if stats['total_size_difference'] != 0:
            # Positive means DB was larger (compression happened)
            if stats['total_size_difference'] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Total size reduction: {self.format_size(stats["total_size_difference"])}'
                    )
                )
            else:
                self.stdout.write(
                    f'Total size increase: {self.format_size(abs(stats["total_size_difference"]))}'
                )

        if dry_run and stats['files_updated'] > 0:
            self.stdout.write('\n' + self.style.WARNING(
                f'DRY RUN: {stats["files_updated"]} files would be updated. '
                'Run without --dry-run to apply changes.'
            ))
        elif stats['files_updated'] > 0:
            self.stdout.write('\n' + self.style.SUCCESS(
                f'Successfully updated {stats["files_updated"]} attachment file sizes!'
            ))
        else:
            self.stdout.write('\n' + self.style.SUCCESS(
                'All file sizes are already correct!'
            ))

    def format_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"

        size_bytes = abs(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0

        return f"{size_bytes:.1f} TB"
