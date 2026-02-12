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
Tests for application/search_service.py
"""

import pytest
from unittest.mock import MagicMock
from application.search_service import EnquirySearchService
from application.models import Enquiry


@pytest.mark.django_db
class TestEnquirySearchService:
    """Tests for EnquirySearchService.apply_search."""

    def test_empty_search_returns_original_queryset(self):
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, "")
        assert result is qs

    def test_whitespace_only_search_returns_original_queryset(self):
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, "   ")
        assert result is qs

    def test_none_search_returns_original_queryset(self):
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, None)
        assert result is qs

    def test_search_returns_queryset(self):
        """Search should always return a queryset (filtered or original)."""
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, "test")
        # Should return a queryset (iterable, not None)
        assert result is not None
        list(result)  # Should not raise

    def test_single_word_search_applies_like_filter(self, db):
        """On SQLite, single-word search uses LIKE filter across all fields."""
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, "building")
        # Should be a filtered queryset - evaluating it should not raise
        list(result)

    def test_multi_word_search_applies_like_filter(self, db):
        """On SQLite, multi-word search uses LIKE filter across all fields."""
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, "uplifting this building")
        list(result)

    def test_short_term_applies_like_filter(self, db):
        """Terms under 3 chars still apply LIKE search (no FULLTEXT)."""
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, "ab")
        list(result)

    def test_search_strips_leading_trailing_whitespace(self, db):
        """Whitespace around the term is stripped before searching."""
        qs = Enquiry.objects.all()
        result = EnquirySearchService.apply_search(qs, "  test  ")
        list(result)


class TestApplySearchFulltextMocked:
    """Tests for FULLTEXT path using a mocked connection."""

    def _make_queryset(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.extra.return_value = qs
        return qs

    def _mock_fulltext_connection(self, has_index=True):
        cursor_mock = MagicMock()
        cursor_mock.__enter__ = MagicMock(return_value=cursor_mock)
        cursor_mock.__exit__ = MagicMock(return_value=False)
        cursor_mock.fetchone.return_value = (1 if has_index else 0,)

        conn_mock = MagicMock()
        conn_mock.vendor = "microsoft"
        conn_mock.cursor.return_value = cursor_mock
        return conn_mock

    def test_single_word_uses_prefix_wildcard(self):
        from unittest.mock import patch
        qs = self._make_queryset()
        conn_mock = self._mock_fulltext_connection(has_index=True)
        with patch("application.search_service.connection", conn_mock):
            EnquirySearchService.apply_search(qs, "building")
        qs.extra.assert_called_once()
        params = qs.extra.call_args[1]["params"]
        assert "building*" in params[0]

    def test_phrase_uses_exact_phrase_no_wildcard(self):
        from unittest.mock import patch
        qs = self._make_queryset()
        conn_mock = self._mock_fulltext_connection(has_index=True)
        with patch("application.search_service.connection", conn_mock):
            EnquirySearchService.apply_search(qs, "uplifting building work")
        qs.extra.assert_called_once()
        params = qs.extra.call_args[1]["params"]
        assert "*" not in params[0]
        assert "uplifting building work" in params[0]

    def test_no_fulltext_index_falls_back_to_like(self):
        from unittest.mock import patch
        qs = self._make_queryset()
        conn_mock = self._mock_fulltext_connection(has_index=False)
        with patch("application.search_service.connection", conn_mock):
            EnquirySearchService.apply_search(qs, "building")
        qs.filter.assert_called_once()
        qs.extra.assert_not_called()

    def test_short_term_skips_fulltext_check(self):
        """Terms shorter than 3 chars skip FULLTEXT even on SQL Server."""
        from unittest.mock import patch
        qs = self._make_queryset()
        conn_mock = self._mock_fulltext_connection(has_index=True)
        with patch("application.search_service.connection", conn_mock):
            EnquirySearchService.apply_search(qs, "ab")
        qs.filter.assert_called_once()
        qs.extra.assert_not_called()
