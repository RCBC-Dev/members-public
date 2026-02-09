"""
Management command to clean up duplicate EnquiryAttachment records.

This fixes the issue where the same file has multiple database records pointing to it,
which occurred before duplicate checking was added to sync_from_live.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from application.models import EnquiryAttachment
from application.file_logger import file_logger


class Command(BaseCommand):
    help = "Clean up duplicate EnquiryAttachment records (same enquiry + file_path)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        self.stdout.write('Searching for duplicate attachment records...\n')
        
        # Find files with duplicate records (same file_path)
        duplicates = EnquiryAttachment.objects.values('file_path').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_files_with_dupes = len(duplicates)
        total_records_to_delete = 0
        deleted_count = 0
        
        if total_files_with_dupes == 0:
            self.stdout.write(self.style.SUCCESS('No duplicate attachment records found!'))
            return
        
        self.stdout.write(f'Found {total_files_with_dupes} files with duplicate records\n')
        
        for dup in duplicates:
            file_path = dup['file_path']
            count = dup['count']
            duplicates_to_delete = count - 1
            total_records_to_delete += duplicates_to_delete
            
            # Get all attachments for this file_path
            attachments = EnquiryAttachment.objects.filter(
                file_path=file_path
            ).select_related('enquiry').order_by('id')
            
            # Keep the first one (oldest), delete the rest
            first_attachment = attachments.first()
            duplicates_list = list(attachments[1:])
            
            enquiry_ref = first_attachment.enquiry.reference if first_attachment.enquiry else 'N/A'
            
            self.stdout.write(
                f'  {enquiry_ref}: {first_attachment.filename}'
            )
            self.stdout.write(
                f'    {count} records → Keeping ID {first_attachment.id}, deleting {duplicates_to_delete} duplicates'
            )
            
            if not dry_run:
                # Delete the duplicates
                for att in duplicates_list:
                    att_id = att.id
                    att.delete()
                    deleted_count += 1
                    
                    # Log the deletion
                    file_logger.log_deletion(
                        file_path=file_path,
                        reason=f'Duplicate attachment record cleanup (kept ID {first_attachment.id})',
                        enquiry_ref=enquiry_ref
                    )
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Files with duplicates:         {total_files_with_dupes}')
        self.stdout.write(f'Duplicate records found:       {total_records_to_delete}')
        
        if dry_run:
            self.stdout.write(f'Would delete:                  {total_records_to_delete}')
            self.stdout.write('\nRun without --dry-run to remove duplicates')
        else:
            self.stdout.write(self.style.SUCCESS(f'Deleted:                       {deleted_count}'))
            self.stdout.write('\nDatabase records now match file count!')
        
        self.stdout.write('=' * 60)

