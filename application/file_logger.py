"""
File operations logger for tracking all file-related operations.

This module provides centralized logging for:
- File deletions (orphaned cleanup)
- File moves/renames
- File size updates
- Image compression operations
- Missing file checks
"""

import logging
from pathlib import Path

from django.conf import settings


class FileOperationsLogger:
    """Logger for file operations with dedicated log file."""

    def __init__(self):
        self.logger = logging.getLogger("file_operations")

        # Only set up if not already configured
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)

            # Create logs directory if it doesn't exist
            log_dir = Path(settings.BASE_DIR) / "logs"
            log_dir.mkdir(exist_ok=True)

            # File handler for file_operations.log
            log_file = log_dir / "file_operations.log"
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)

            # Format: timestamp | operation | details
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)

    def log_deletion(self, file_path, reason, enquiry_ref=None, backup_path=None):
        """Log file deletion."""
        msg = f"DELETE | {file_path}"
        if enquiry_ref:
            msg += f" | Enquiry: {enquiry_ref}"
        msg += f" | Reason: {reason}"
        if backup_path:
            msg += f" | Backup: {backup_path}"
        self.logger.info(msg)

    def log_orphan_cleanup(self, deleted_count, total_size, backup_dir=None):
        """Log orphaned file cleanup operation."""
        msg = f"ORPHAN_CLEANUP | Deleted: {deleted_count} files | Size: {total_size}"
        if backup_dir:
            msg += f" | Backup: {backup_dir}"
        self.logger.info(msg)

    def log_compression(
        self, file_path, original_size, new_size, savings_percent, enquiry_ref=None
    ):
        """Log image compression."""
        msg = f"COMPRESS | {file_path} | {original_size} → {new_size} | Saved: {savings_percent}%"
        if enquiry_ref:
            msg += f" | Enquiry: {enquiry_ref}"
        self.logger.info(msg)

    def log_resize(self, file_path, old_dimensions, new_dimensions, enquiry_ref=None):
        """Log image resize."""
        msg = f"RESIZE | {file_path} | {old_dimensions} → {new_dimensions}"
        if enquiry_ref:
            msg += f" | Enquiry: {enquiry_ref}"
        self.logger.info(msg)

    def log_size_update(self, file_path, old_size, new_size, enquiry_ref=None):
        """Log file size update in database."""
        msg = f"SIZE_UPDATE | {file_path} | DB: {old_size} → Actual: {new_size}"
        if enquiry_ref:
            msg += f" | Enquiry: {enquiry_ref}"
        self.logger.info(msg)

    def log_move(self, old_path, new_path, reason=None):
        """Log file move/rename."""
        msg = f"MOVE | {old_path} → {new_path}"
        if reason:
            msg += f" | Reason: {reason}"
        self.logger.info(msg)

    def log_copy(self, source_path, dest_path, reason=None):
        """Log file copy operation."""
        msg = f"COPY | {source_path} → {dest_path}"
        if reason:
            msg += f" | Reason: {reason}"
        self.logger.info(msg)

    def log_delete(self, file_path, reason=None):
        """Log file deletion (simpler version of log_deletion)."""
        msg = f"DELETE | {file_path}"
        if reason:
            msg += f" | Reason: {reason}"
        self.logger.info(msg)

    def log_missing_check(self, total_checked, missing_count, corrupted_count):
        """Log missing file check results."""
        msg = f"MISSING_CHECK | Checked: {total_checked} | Missing: {missing_count} | Corrupted: {corrupted_count}"
        self.logger.info(msg)

    def log_error(self, operation, file_path, error_msg):
        """Log file operation error."""
        msg = f"ERROR | {operation} | {file_path} | {error_msg}"
        self.logger.error(msg)


# Singleton instance
file_logger = FileOperationsLogger()
