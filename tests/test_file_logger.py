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
Tests for application/file_logger.py
"""

import pytest
from unittest.mock import patch, MagicMock
from application.file_logger import FileOperationsLogger


def make_logger():
    """Create a FileOperationsLogger with a mock underlying logger."""
    logger = FileOperationsLogger.__new__(FileOperationsLogger)
    logger.logger = MagicMock()
    return logger


class TestLogDeletion:
    """Tests for FileOperationsLogger.log_deletion."""

    def test_basic_deletion_logged(self):
        fol = make_logger()
        fol.log_deletion("/media/file.pdf", "orphaned")
        fol.logger.info.assert_called_once()
        msg = fol.logger.info.call_args[0][0]
        assert "DELETE" in msg
        assert "/media/file.pdf" in msg
        assert "orphaned" in msg

    def test_includes_enquiry_ref_when_provided(self):
        fol = make_logger()
        fol.log_deletion("/media/file.pdf", "cleanup", enquiry_ref="ENQ-001")
        msg = fol.logger.info.call_args[0][0]
        assert "ENQ-001" in msg

    def test_includes_backup_path_when_provided(self):
        fol = make_logger()
        fol.log_deletion("/media/file.pdf", "cleanup", backup_path="/backup/file.pdf")
        msg = fol.logger.info.call_args[0][0]
        assert "/backup/file.pdf" in msg

    def test_no_enquiry_ref_or_backup(self):
        fol = make_logger()
        fol.log_deletion("/media/f.pdf", "reason")
        msg = fol.logger.info.call_args[0][0]
        assert "Enquiry" not in msg
        assert "Backup" not in msg


class TestLogOrphanCleanup:
    """Tests for FileOperationsLogger.log_orphan_cleanup."""

    def test_basic_cleanup_logged(self):
        fol = make_logger()
        fol.log_orphan_cleanup(5, "10MB")
        msg = fol.logger.info.call_args[0][0]
        assert "ORPHAN_CLEANUP" in msg
        assert "5" in msg
        assert "10MB" in msg

    def test_includes_backup_dir_when_provided(self):
        fol = make_logger()
        fol.log_orphan_cleanup(3, "5MB", backup_dir="/backup")
        msg = fol.logger.info.call_args[0][0]
        assert "/backup" in msg


class TestLogCompression:
    """Tests for FileOperationsLogger.log_compression."""

    def test_compression_logged_with_stats(self):
        fol = make_logger()
        fol.log_compression("/media/img.jpg", 1000, 500, 50)
        msg = fol.logger.info.call_args[0][0]
        assert "COMPRESS" in msg
        assert "/media/img.jpg" in msg
        assert "1000" in msg
        assert "500" in msg
        assert "50" in msg

    def test_includes_enquiry_ref(self):
        fol = make_logger()
        fol.log_compression("/media/img.jpg", 1000, 500, 50, enquiry_ref="ENQ-42")
        msg = fol.logger.info.call_args[0][0]
        assert "ENQ-42" in msg


class TestLogResize:
    """Tests for FileOperationsLogger.log_resize."""

    def test_resize_logged(self):
        fol = make_logger()
        fol.log_resize("/media/img.jpg", "1920x1080", "800x600")
        msg = fol.logger.info.call_args[0][0]
        assert "RESIZE" in msg
        assert "1920x1080" in msg
        assert "800x600" in msg

    def test_includes_enquiry_ref(self):
        fol = make_logger()
        fol.log_resize("/media/img.jpg", "800x600", "400x300", enquiry_ref="ENQ-5")
        msg = fol.logger.info.call_args[0][0]
        assert "ENQ-5" in msg


class TestLogSizeUpdate:
    """Tests for FileOperationsLogger.log_size_update."""

    def test_size_update_logged(self):
        fol = make_logger()
        fol.log_size_update("/media/file.pdf", 0, 2048)
        msg = fol.logger.info.call_args[0][0]
        assert "SIZE_UPDATE" in msg
        assert "/media/file.pdf" in msg


class TestLogMove:
    """Tests for FileOperationsLogger.log_move."""

    def test_move_logged(self):
        fol = make_logger()
        fol.log_move("/old/path.pdf", "/new/path.pdf")
        msg = fol.logger.info.call_args[0][0]
        assert "MOVE" in msg
        assert "/old/path.pdf" in msg
        assert "/new/path.pdf" in msg

    def test_includes_reason_when_provided(self):
        fol = make_logger()
        fol.log_move("/old.pdf", "/new.pdf", reason="reorganize")
        msg = fol.logger.info.call_args[0][0]
        assert "reorganize" in msg


class TestLogCopy:
    """Tests for FileOperationsLogger.log_copy."""

    def test_copy_logged(self):
        fol = make_logger()
        fol.log_copy("/src.pdf", "/dst.pdf")
        msg = fol.logger.info.call_args[0][0]
        assert "COPY" in msg
        assert "/src.pdf" in msg
        assert "/dst.pdf" in msg

    def test_includes_reason(self):
        fol = make_logger()
        fol.log_copy("/src.pdf", "/dst.pdf", reason="backup")
        msg = fol.logger.info.call_args[0][0]
        assert "backup" in msg


class TestLogDelete:
    """Tests for FileOperationsLogger.log_delete (simpler version)."""

    def test_delete_logged(self):
        fol = make_logger()
        fol.log_delete("/media/file.pdf")
        msg = fol.logger.info.call_args[0][0]
        assert "DELETE" in msg
        assert "/media/file.pdf" in msg

    def test_includes_reason(self):
        fol = make_logger()
        fol.log_delete("/media/file.pdf", reason="expired")
        msg = fol.logger.info.call_args[0][0]
        assert "expired" in msg


class TestLogMissingCheck:
    """Tests for FileOperationsLogger.log_missing_check."""

    def test_missing_check_logged(self):
        fol = make_logger()
        fol.log_missing_check(100, 5, 2)
        msg = fol.logger.info.call_args[0][0]
        assert "MISSING_CHECK" in msg
        assert "100" in msg
        assert "5" in msg
        assert "2" in msg


class TestLogError:
    """Tests for FileOperationsLogger.log_error."""

    def test_error_logged_as_error(self):
        fol = make_logger()
        fol.log_error("DELETE", "/media/file.pdf", "Permission denied")
        fol.logger.error.assert_called_once()
        msg = fol.logger.error.call_args[0][0]
        assert "ERROR" in msg
        assert "DELETE" in msg
        assert "/media/file.pdf" in msg
        assert "Permission denied" in msg
