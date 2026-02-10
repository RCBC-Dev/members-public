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
Centralized search service for the Members Enquiries System.

This module provides a single source of truth for enquiry search logic,
supporting both SQL Server FULLTEXT search and SQLite LIKE fallback.
"""

from django.db import connection
from django.db.models import Q


class EnquirySearchService:
    """
    Centralized search logic for enquiries across all views.

    Provides intelligent search that:
    - Uses SQL Server FULLTEXT search when available for performance
    - Handles both single-word and multi-word phrase searches correctly
    - Falls back to LIKE search for SQLite or when FULLTEXT is unavailable
    - Searches across reference, title, and description fields
    """

    @staticmethod
    def apply_search(queryset, search_value):
        """
        Apply intelligent FULLTEXT or LIKE search to enquiry queryset.

        This method automatically detects the database backend and applies the
        most appropriate search strategy:
        - SQL Server with FULLTEXT: Uses CONTAINS() with smart wildcard handling
        - SQLite or no index: Falls back to case-insensitive LIKE search

        For SQL Server FULLTEXT search:
        - Multi-word phrases (e.g., "uplifting this building"): Searches for exact phrase
        - Single words (e.g., "building"): Uses prefix wildcard for partial matching

        Args:
            queryset: Enquiry queryset to filter
            search_value: Search term (supports phrases and single words)

        Returns:
            Filtered queryset with search applied, or original queryset if search_value is empty

        Example:
            >>> from application.models import Enquiry
            >>> queryset = Enquiry.objects.all()
            >>> results = EnquirySearchService.apply_search(queryset, "uplifting this building")
            >>> # Returns enquiries containing the exact phrase
        """
        if not search_value or not search_value.strip():
            return queryset

        search_value = search_value.strip()
        use_fulltext = False

        # Check for SQL Server FULLTEXT index availability
        if connection.vendor == 'microsoft' and len(search_value) >= 3:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM sys.fulltext_indexes
                    WHERE object_id = OBJECT_ID('members_app_enquiry')
                """)
                if cursor.fetchone()[0] > 0:
                    use_fulltext = True

        if use_fulltext:
            # SQL Server FULLTEXT search with smart wildcard handling
            # For phrases (multiple words): don't use wildcard as it breaks phrase matching
            # For single words: use wildcard for prefix matching (e.g., "build*" finds "building")
            if ' ' in search_value:
                # Multi-word phrase search - use exact phrase without wildcard
                search_param = f'"{search_value}"'
            else:
                # Single word search - use wildcard for prefix matching
                search_param = f'"{search_value}*"'

            return queryset.extra(
                where=["CONTAINS((members_app_enquiry.reference, members_app_enquiry.title, members_app_enquiry.description), %s)"],
                params=[search_param]
            )
        else:
            # Fallback to LIKE search (SQLite, short terms, or no FULLTEXT index)
            # This works across all database backends
            return queryset.filter(
                Q(reference__icontains=search_value) |
                Q(title__icontains=search_value) |
                Q(description__icontains=search_value)
            )
