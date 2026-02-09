"""
Management command to analyze and optimize Django Summernote image attachments.
This command can analyze file sizes, compress large images, and clean up storage.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
import os
import glob
from PIL import Image, ImageOps
import math


class Command(BaseCommand):
    help = 'Analyze and optimize Django Summernote image attachments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--analyze',
            action='store_true',
            help='Only analyze file sizes without making changes',
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress images larger than the specified threshold',
        )
        parser.add_argument(
            '--max-size-mb',
            type=float,
            default=1.0,
            help='Maximum file size in MB before compression (default: 1.0)',
        )
        parser.add_argument(
            '--quality',
            type=int,
            default=85,
            help='JPEG compression quality (1-100, default: 85)',
        )
        parser.add_argument(
            '--max-dimension',
            type=int,
            default=1920,
            help='Maximum width/height dimension in pixels (default: 1920)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--cleanup-backups',
            action='store_true',
            help='Remove existing .backup files created by previous runs',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.HTTP_INFO('Enquiry Image Optimizer')
        )

        media_root = getattr(settings, 'MEDIA_ROOT', 'media')

        # Scan BOTH django-summernote and enquiry_photos directories
        directories_to_scan = [
            os.path.join(media_root, 'django-summernote'),
            os.path.join(media_root, 'enquiry_photos'),
        ]

        # Filter to only existing directories
        existing_dirs = [d for d in directories_to_scan if os.path.exists(d)]

        if not existing_dirs:
            self.stdout.write(
                self.style.ERROR('No image directories found (django-summernote or enquiry_photos)')
            )
            return

        self.stdout.write(f"Analyzing directories:")
        for directory in existing_dirs:
            self.stdout.write(f"  - {directory}")

        # Get all image files from all directories
        image_files = []
        for directory in existing_dirs:
            image_files.extend(self.find_all_images(directory))
        
        if not image_files:
            self.stdout.write(
                self.style.WARNING('No image files found in image directories')
            )
            return
        
        # Analyze files
        analysis = self.analyze_images(image_files, options['max_size_mb'])
        self.display_analysis(analysis)
        
        # Handle cleanup backups first if requested
        if options['cleanup_backups']:
            self.cleanup_existing_backups(summernote_path, options['dry_run'])
        
        # Compress if requested
        if options['compress']:
            if options['dry_run']:
                self.stdout.write('\nDRY RUN MODE - No files will be modified')
                self.show_compression_plan(analysis, options)
            else:
                self.compress_large_images(analysis, options)
        elif options['analyze']:
            self.stdout.write('\nAnalysis complete - no compression requested')
        else:
            self.stdout.write('\nUse --compress to optimize large images')
            self.stdout.write('Use --analyze for analysis only')
            if options['cleanup_backups']:
                self.stdout.write('Backup cleanup completed')

    def find_all_images(self, summernote_path):
        """Find all image files in the Summernote directory structure"""
        image_files = set()  # Use set to avoid duplicates
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        
        # Search all subdirectories (organized by date)
        for root, dirs, files in os.walk(summernote_path):
            for file in files:
                file_lower = file.lower()
                if any(file_lower.endswith(ext) for ext in image_extensions):
                    image_files.add(os.path.join(root, file))
        
        return list(image_files)

    def analyze_images(self, image_files, max_size_mb):
        """Analyze image files and categorize by size"""
        analysis = {
            'total_files': len(image_files),
            'total_size_mb': 0,
            'large_files': [],
            'medium_files': [],
            'small_files': [],
            'error_files': [],
            'by_date': {},
            'by_type': {}
        }
        
        max_size_bytes = max_size_mb * 1024 * 1024
        medium_threshold = max_size_bytes / 2  # Half of max size
        
        for file_path in image_files:
            try:
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                analysis['total_size_mb'] += file_size_mb
                
                # Extract date from path
                path_parts = file_path.split(os.sep)
                date_folder = None
                for part in path_parts:
                    if part.startswith('2024-') or part.startswith('2025-'):
                        date_folder = part
                        break
                
                if date_folder:
                    if date_folder not in analysis['by_date']:
                        analysis['by_date'][date_folder] = {'count': 0, 'size_mb': 0}
                    analysis['by_date'][date_folder]['count'] += 1
                    analysis['by_date'][date_folder]['size_mb'] += file_size_mb
                
                # File type
                ext = os.path.splitext(file_path)[1].lower()
                if ext not in analysis['by_type']:
                    analysis['by_type'][ext] = {'count': 0, 'size_mb': 0}
                analysis['by_type'][ext]['count'] += 1
                analysis['by_type'][ext]['size_mb'] += file_size_mb
                
                # Size categories
                file_info = {
                    'path': file_path,
                    'size_bytes': file_size,
                    'size_mb': file_size_mb,
                    'date': date_folder
                }
                
                if file_size > max_size_bytes:
                    analysis['large_files'].append(file_info)
                elif file_size > medium_threshold:
                    analysis['medium_files'].append(file_info)
                else:
                    analysis['small_files'].append(file_info)
                    
            except Exception as e:
                analysis['error_files'].append({'path': file_path, 'error': str(e)})
        
        return analysis

    def display_analysis(self, analysis):
        """Display comprehensive analysis results"""
        self.stdout.write('\nIMAGE ANALYSIS RESULTS')
        self.stdout.write('=' * 60)
        
        self.stdout.write(f"Total files: {analysis['total_files']:,}")
        self.stdout.write(f"Total size: {analysis['total_size_mb']:.1f} MB")
        self.stdout.write(f"Average size: {analysis['total_size_mb']/max(analysis['total_files'],1):.1f} MB per file")
        
        # Size breakdown
        self.stdout.write(f"\nSIZE BREAKDOWN:")
        self.stdout.write(f"Large files (>1MB): {len(analysis['large_files']):,}")
        self.stdout.write(f"Medium files (0.5-1MB): {len(analysis['medium_files']):,}")
        self.stdout.write(f"Small files (<0.5MB): {len(analysis['small_files']):,}")
        
        if analysis['error_files']:
            self.stdout.write(f"Error files: {len(analysis['error_files'])}")
        
        # Top large files
        if analysis['large_files']:
            self.stdout.write(f"\nTOP 10 LARGEST FILES:")
            large_sorted = sorted(analysis['large_files'], key=lambda x: x['size_mb'], reverse=True)
            for i, file_info in enumerate(large_sorted[:10]):
                filename = os.path.basename(file_info['path'])
                self.stdout.write(f"  {i+1:2d}. {filename} - {file_info['size_mb']:.1f} MB ({file_info['date']})")
        
        # By date
        if analysis['by_date']:
            self.stdout.write(f"\nBY DATE (Top 10):")
            date_sorted = sorted(analysis['by_date'].items(), key=lambda x: x[1]['size_mb'], reverse=True)
            for date, info in date_sorted[:10]:
                self.stdout.write(f"  {date}: {info['count']:3d} files, {info['size_mb']:6.1f} MB")
        
        # By file type
        if analysis['by_type']:
            self.stdout.write(f"\nBY FILE TYPE:")
            type_sorted = sorted(analysis['by_type'].items(), key=lambda x: x[1]['size_mb'], reverse=True)
            for ext, info in type_sorted:
                avg_size = info['size_mb'] / max(info['count'], 1)
                self.stdout.write(f"  {ext:6s}: {info['count']:4d} files, {info['size_mb']:6.1f} MB (avg: {avg_size:.1f} MB)")

    def show_compression_plan(self, analysis, options):
        """Show what compression would do"""
        self.stdout.write('\nCOMPRESSION PLAN:')
        self.stdout.write('=' * 60)
        
        files_to_compress = analysis['large_files']
        if not files_to_compress:
            self.stdout.write('No files need compression')
            return
            
        total_original = sum(f['size_mb'] for f in files_to_compress)
        estimated_savings = total_original * 0.6  # Estimate 60% size reduction
        
        self.stdout.write(f"Files to compress: {len(files_to_compress)}")
        self.stdout.write(f"Original size: {total_original:.1f} MB")
        self.stdout.write(f"Estimated after: {total_original - estimated_savings:.1f} MB")
        self.stdout.write(f"Estimated savings: {estimated_savings:.1f} MB")
        
        self.stdout.write(f"\nCompression settings:")
        self.stdout.write(f"  Max file size: {options['max_size_mb']} MB")
        self.stdout.write(f"  JPEG quality: {options['quality']}%")
        self.stdout.write(f"  Max dimension: {options['max_dimension']}px")

    def compress_large_images(self, analysis, options):
        """Compress images that are larger than the threshold"""
        files_to_compress = analysis['large_files']
        
        if not files_to_compress:
            self.stdout.write('No files need compression')
            return
            
        self.stdout.write(f'\nCOMPRESSING {len(files_to_compress)} IMAGES')
        self.stdout.write('=' * 60)
        
        compressed_count = 0
        total_saved_mb = 0
        
        for file_info in files_to_compress:
            try:
                original_size = file_info['size_mb']
                new_size_mb = self.compress_image(file_info['path'], options)
                
                if new_size_mb < original_size:
                    saved_mb = original_size - new_size_mb
                    total_saved_mb += saved_mb
                    compressed_count += 1
                    
                    filename = os.path.basename(file_info['path'])
                    self.stdout.write(
                        f"OK {filename}: {original_size:.1f} MB -> {new_size_mb:.1f} MB "
                        f"(saved {saved_mb:.1f} MB)"
                    )
                else:
                    filename = os.path.basename(file_info['path'])
                    self.stdout.write(f"SKIP {filename}: No compression benefit")
                    
            except Exception as e:
                filename = os.path.basename(file_info['path'])
                self.stdout.write(f"ERROR {filename}: {str(e)}")
        
        self.stdout.write(f'\nCOMPRESSION SUMMARY:')
        self.stdout.write(f"Files compressed: {compressed_count}/{len(files_to_compress)}")
        self.stdout.write(f"Total space saved: {total_saved_mb:.1f} MB")

    def compress_image(self, file_path, options):
        """Compress a single image file with temporary backup for safety"""
        import shutil
        
        # Create temporary backup for safety
        backup_path = file_path + '.backup'
        shutil.copy2(file_path, backup_path)
        
        try:
            # Open and compress image
            with Image.open(file_path) as img:
                # Fix orientation based on EXIF data
                img = ImageOps.exif_transpose(img)
            
            # Resize if too large
            max_dim = options['max_dimension']
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary (for JPEG saving)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, 'white')
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
                # Save with compression
                img.save(
                    file_path, 
                    'JPEG', 
                    quality=options['quality'],
                    optimize=True,
                    progressive=True
                )
            
            # Compression successful - remove backup
            os.remove(backup_path)
            
            # Return new file size
            new_size = os.path.getsize(file_path)
            return new_size / (1024 * 1024)
            
        except Exception as e:
            # Compression failed - restore from backup
            if os.path.exists(backup_path):
                shutil.move(backup_path, file_path)
            raise e

    def cleanup_existing_backups(self, summernote_path, dry_run=False):
        """Clean up existing .backup files from previous runs"""
        self.stdout.write('\nCLEANING UP EXISTING BACKUP FILES')
        self.stdout.write('=' * 50)
        
        backup_files = []
        backup_size_mb = 0
        
        # Find all backup files
        for root, dirs, files in os.walk(summernote_path):
            for file in files:
                if file.endswith('.backup'):
                    backup_path = os.path.join(root, file)
                    original_path = backup_path[:-7]  # Remove '.backup'
                    
                    # Only delete if original exists
                    if os.path.exists(original_path):
                        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
                        backup_files.append((backup_path, size_mb))
                        backup_size_mb += size_mb
        
        if not backup_files:
            self.stdout.write('No backup files found')
            return
            
        self.stdout.write(f"Found {len(backup_files)} backup files ({backup_size_mb:.1f} MB)")
        
        if dry_run:
            self.stdout.write('DRY RUN - Would delete these backup files')
            for backup_path, size_mb in backup_files[:10]:  # Show first 10
                filename = os.path.basename(backup_path)
                self.stdout.write(f"  {filename} ({size_mb:.1f} MB)")
            if len(backup_files) > 10:
                self.stdout.write(f"  ... and {len(backup_files) - 10} more")
        else:
            deleted_count = 0
            freed_mb = 0
            
            for backup_path, size_mb in backup_files:
                try:
                    os.remove(backup_path)
                    deleted_count += 1
                    freed_mb += size_mb
                except Exception as e:
                    filename = os.path.basename(backup_path)
                    self.stdout.write(f"ERROR deleting {filename}: {e}")
            
            self.stdout.write(f"Deleted {deleted_count} backup files")
            self.stdout.write(f"Freed {freed_mb:.1f} MB of space")

    def get_summernote_db_stats(self):
        """Get statistics from the Summernote attachment database table"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as total_attachments,
                           MIN(uploaded) as earliest_upload,
                           MAX(uploaded) as latest_upload
                    FROM django_summernote_attachment
                """)
                return cursor.fetchone()
        except Exception as e:
            return None