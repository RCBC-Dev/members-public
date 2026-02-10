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
Django management command to clean up orphaned files.

This command identifies and removes files that are not linked to any enquiry
attachment in the database. It provides safety features including dry-run mode,
backup creation, and detailed logging.

Usage:
    python manage.py cleanup_orphaned_files --dry-run
    python manage.py cleanup_orphaned_files --backup
    python manage.py cleanup_orphaned_files --older-than 30
    python manage.py cleanup_orphaned_files --confirm
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from application.models import EnquiryAttachment
from application.file_logger import file_logger


class Command(BaseCommand):
    help = 'Clean up orphaned files not linked to any enquiry'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Create backup of files before deletion',
        )
        parser.add_argument(
            '--backup-dir',
            type=str,
            default='orphaned_files_backup',
            help='Directory to store backups (default: orphaned_files_backup)',
        )
        parser.add_argument(
            '--older-than',
            type=int,
            help='Only delete files older than N days',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without interactive prompt',
        )
        parser.add_argument(
            '--directory',
            type=str,
            help='Limit cleanup to specific directory',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.HTTP_INFO('Orphaned File Cleanup Tool')
        )
        self.stdout.write('=' * 60)
        
        # Safety check
        if not options['dry_run'] and not options['confirm']:
            self.stdout.write(
                self.style.WARNING('This will permanently delete files!')
            )
            self.stdout.write('Use --dry-run to preview or --confirm to proceed')
            return
        
        # Initialize tracking
        self.deleted_count = 0
        self.deleted_size = 0
        self.backed_up_count = 0
        self.errors = []
        
        # Get media root
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f'Media directory not found: {media_root}')
        
        # Create backup directory if needed
        if options['backup'] and not options['dry_run']:
            backup_dir = Path(options['backup_dir'])
            backup_dir.mkdir(exist_ok=True)
            self.stdout.write(f'Backup directory: {backup_dir}')
        
        # Find orphaned files
        orphaned_files = self.find_orphaned_files(options)
        
        if not orphaned_files:
            self.stdout.write(
                self.style.SUCCESS('No orphaned files found!')
            )
            return
        
        # Display summary
        total_size = sum(f['size'] for f in orphaned_files)
        self.stdout.write(f'Found {len(orphaned_files)} orphaned files')
        self.stdout.write(f'Total size: {self.format_size(total_size)}')
        
        if options['dry_run']:
            self.stdout.write('\nDRY RUN - Files that would be deleted:')
            self.display_orphaned_files(orphaned_files)
            return
        
        # Confirm deletion
        if not options['confirm']:
            response = input(f'\nDelete {len(orphaned_files)} files? (y/N): ')
            if response.lower() != 'y':
                self.stdout.write('Cleanup cancelled')
                return
        
        # Process files
        self.process_orphaned_files(orphaned_files, options)
        
        # Display results
        self.display_results()

    def find_orphaned_files(self, options):
        """Find all orphaned files in enquiry directories."""
        self.stdout.write('Searching for orphaned files...')
        
        # Get all attachment file paths from database
        db_file_paths = set()
        for attachment in EnquiryAttachment.objects.all():
            if attachment.file_path:
                # Normalize path separators
                normalized_path = attachment.file_path.replace('\\', '/')
                db_file_paths.add(normalized_path)
        
        self.stdout.write(f'Found {len(db_file_paths)} files in database')
        
        # Determine directories to check
        media_root = Path(settings.MEDIA_ROOT)
        if options['directory']:
            directories = [media_root / options['directory']]
        else:
            # IMPORTANT: Only check enquiry directories, NOT django-summernote
            # Summernote images are embedded in enquiry descriptions and cannot be
            # detected as orphans without scanning all enquiry content
            directories = [
                media_root / 'enquiry_photos',
                media_root / 'enquiry_attachments'
            ]
        
        directories = [d for d in directories if d.exists()]
        
        # Find orphaned files
        orphaned_files = []
        cutoff_date = None
        
        if options['older_than']:
            cutoff_date = timezone.now() - timedelta(days=options['older_than'])
            self.stdout.write(f'Only considering files older than {cutoff_date.date()}')
        
        for directory in directories:
            self.stdout.write(f'Checking directory: {directory}')
            
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = Path(root) / file
                    
                    try:
                        # Get relative path from media root
                        relative_path = file_path.relative_to(media_root)
                        normalized_relative = str(relative_path).replace('\\', '/')
                        
                        # Check if file is in database
                        if normalized_relative not in db_file_paths:
                            # Get file info
                            stat = file_path.stat()
                            modified_time = datetime.fromtimestamp(stat.st_mtime)
                            
                            # Check age filter
                            if cutoff_date and timezone.make_aware(modified_time) > cutoff_date:
                                continue
                            
                            orphaned_files.append({
                                'path': file_path,
                                'relative_path': normalized_relative,
                                'size': stat.st_size,
                                'modified': modified_time,
                                'extension': file_path.suffix.lower()
                            })
                    
                    except (ValueError, OSError) as e:
                        self.errors.append(f'Error processing {file_path}: {e}')
        
        return orphaned_files

    def process_orphaned_files(self, orphaned_files, options):
        """Process (backup and delete) orphaned files."""
        backup_dir = Path(options['backup_dir']) if options['backup'] else None

        for file_info in orphaned_files:
            file_path = file_info['path']

            try:
                backup_path_str = None

                # Create backup if requested
                if options['backup']:
                    backup_path = backup_dir / file_info['relative_path']
                    backup_path.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(file_path, backup_path)
                    self.backed_up_count += 1
                    backup_path_str = str(backup_path)
                    self.stdout.write(f'Backed up: {file_info["relative_path"]}')

                # Delete the file
                file_path.unlink()
                self.deleted_count += 1
                self.deleted_size += file_info['size']

                # Log the deletion
                file_logger.log_deletion(
                    file_path=file_info['relative_path'],
                    reason="Orphaned - no database record",
                    enquiry_ref=None,
                    backup_path=backup_path_str
                )

                # Remove empty directories
                self.cleanup_empty_directories(file_path.parent)

            except Exception as e:
                error_msg = f'Error processing {file_path}: {e}'
                self.errors.append(error_msg)
                self.stdout.write(
                    self.style.ERROR(error_msg)
                )

    def cleanup_empty_directories(self, directory):
        """Remove empty directories recursively."""
        try:
            # Only remove if directory is empty
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
                self.stdout.write(f'Removed empty directory: {directory}')
                
                # Recursively check parent directory
                if directory.parent != Path(settings.MEDIA_ROOT):
                    self.cleanup_empty_directories(directory.parent)
        
        except OSError:
            # Directory not empty or permission error
            pass

    def display_orphaned_files(self, orphaned_files):
        """Display list of orphaned files."""
        # Group by directory for better display
        by_directory = {}
        for file_info in orphaned_files:
            dir_path = str(file_info['path'].parent)
            if dir_path not in by_directory:
                by_directory[dir_path] = []
            by_directory[dir_path].append(file_info)
        
        for directory, files in sorted(by_directory.items()):
            self.stdout.write(f'\n{directory}:')
            for file_info in sorted(files, key=lambda x: x['path'].name):
                age_days = (datetime.now() - file_info['modified']).days
                self.stdout.write(
                    f'  {file_info["path"].name} '
                    f'({self.format_size(file_info["size"])}, '
                    f'{age_days} days old)'
                )

    def display_results(self):
        """Display cleanup results."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('CLEANUP RESULTS')
        self.stdout.write('=' * 60)

        self.stdout.write(f'Files deleted: {self.deleted_count}')
        self.stdout.write(f'Space freed: {self.format_size(self.deleted_size)}')

        if self.backed_up_count > 0:
            self.stdout.write(f'Files backed up: {self.backed_up_count}')

        if self.errors:
            self.stdout.write(f'Errors encountered: {len(self.errors)}')
            for error in self.errors[:5]:  # Show first 5 errors
                self.stdout.write(f'  {error}')
            if len(self.errors) > 5:
                self.stdout.write(f'  ... and {len(self.errors) - 5} more errors')

        # Log the overall cleanup operation
        if self.deleted_count > 0:
            file_logger.log_orphan_cleanup(
                deleted_count=self.deleted_count,
                total_size=self.format_size(self.deleted_size),
                backup_dir=None  # Backup directory is logged per-file
            )

        if self.deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS('Cleanup completed successfully!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('No files were deleted')
            )

    def format_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} TB"
