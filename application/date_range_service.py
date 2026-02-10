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
Unified Date Range Service for the Members Enquiries System.

This module consolidates all date range calculation logic into a single service,
eliminating duplication across services.py, class_views.py, and other modules.
"""

from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from typing import Dict, Optional, Tuple, Union
from urllib.parse import urlencode

from .date_utils import DateRange, get_preset_date_range


class DateRangeService:
    """
    Centralized service for all date range operations.
    
    This service consolidates functionality from:
    - EnquiryFilterService._dates_match_predefined_range
    - EnquiryFilterMixin._dates_match_predefined_range  
    - DateRangeUtility methods
    - Various date calculation utilities
    """
    
    # Standard date range types
    PRESET_RANGES = ['3months', '6months', '12months', 'all']
    
    # Default tolerance for date matching (in days)
    DATE_MATCH_TOLERANCE = 1
    
    @classmethod
    def dates_match_predefined_range(cls, date_from_str: str, date_to_str: str) -> bool:
        """
        Check if the provided dates match any predefined range.
        
        Consolidates logic from EnquiryFilterService and EnquiryFilterMixin.
        
        Args:
            date_from_str: Date string in 'YYYY-MM-DD' format
            date_to_str: Date string in 'YYYY-MM-DD' format
            
        Returns:
            True if dates match a predefined range, False otherwise
        """
        if not date_from_str or not date_to_str:
            return False

        try:
            # Parse the provided dates
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()

            # Check against predefined ranges using centralized calculation
            for range_type in ['3months', '6months', '12months']:
                date_range_info = get_preset_date_range(range_type, timezone_aware=False)
                expected_from = datetime.strptime(date_range_info.date_from_str, '%Y-%m-%d').date()
                expected_to = datetime.strptime(date_range_info.date_to_str, '%Y-%m-%d').date()

                # Allow tolerance for "today" since it might change between requests
                if (abs((date_from - expected_from).days) <= cls.DATE_MATCH_TOLERANCE and
                    abs((date_to - expected_to).days) <= cls.DATE_MATCH_TOLERANCE):
                    return True

            return False
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def get_default_filter_params(cls, status: str = '', date_range: str = '12months') -> Dict[str, str]:
        """
        Get default filter parameters for enquiry filtering.
        
        Args:
            status: Default status filter
            date_range: Default date range
            
        Returns:
            Dictionary of default filter parameters
        """
        if date_range in cls.PRESET_RANGES and date_range != 'all':
            # Use centralized date calculation
            date_range_info = get_preset_date_range(date_range, timezone_aware=False)
            return {
                'status': status,
                'date_range': date_range,
                'date_from': date_range_info.date_from_str,
                'date_to': date_range_info.date_to_str
            }
        else:
            return {
                'status': status,
                'date_range': date_range
            }
    
    @classmethod
    def get_default_filter_redirect(cls, request_path: str, status: str = '',
                                  date_range: str = '3months') -> HttpResponseRedirect:
        """
        Get redirect response with default filter parameters.
        
        Replaces EnquiryFilterService.get_default_filter_redirect.
        
        Args:
            request_path: Current request path
            status: Default status filter
            date_range: Default date range
            
        Returns:
            HttpResponseRedirect with default parameters
        """
        default_params = cls.get_default_filter_params(status, date_range)
        return HttpResponseRedirect(f"{request_path}?{urlencode(default_params)}")
    
    @classmethod
    def clean_url_parameters(cls, request_get_params) -> Tuple[Dict[str, str], bool]:
        """
        Clean up URL parameters, removing empty values and handling custom dates.
        
        Consolidates logic from EnquiryFilterService.clean_url_parameters.
        
        Args:
            request_get_params: Request GET parameters
            
        Returns:
            Tuple of (clean_params dict, needs_redirect boolean)
        """
        clean_params = {}
        has_empty_params = False

        date_range = request_get_params.get('date_range', '12months')
        date_from = request_get_params.get('date_from', '')
        date_to = request_get_params.get('date_to', '')

        # First, collect all non-empty parameters
        for key, value in request_get_params.items():
            if value and str(value).strip():
                clean_params[key] = value
            elif key == 'date_range':
                # Always preserve explicit date_range values
                clean_params[key] = value
            else:
                has_empty_params = True

        # If no date_range is provided and no custom dates, default to '12months'
        if 'date_range' not in clean_params and not date_from and not date_to:
            clean_params['date_range'] = '12months'
            has_empty_params = True

        return clean_params, has_empty_params
    
    @classmethod
    def apply_date_filters(cls, queryset, filter_form):
        """
        Apply date filtering logic to a queryset.
        
        Consolidates date filtering from EnquiryFilterService and EnquiryFilterMixin.
        
        Args:
            queryset: Django queryset to filter
            filter_form: Validated form with date filter data
            
        Returns:
            Filtered queryset
        """
        if not filter_form.is_valid():
            return queryset
            
        date_range = filter_form.cleaned_data.get('date_range')
        date_from_custom = filter_form.cleaned_data.get('date_from')
        date_to_custom = filter_form.cleaned_data.get('date_to')

        # Apply standardized date filtering
        if date_range == 'custom':
            # Custom date range - use explicit date_from/date_to
            if date_from_custom:
                queryset = queryset.filter(created_at__date__gte=date_from_custom)
            if date_to_custom:
                queryset = queryset.filter(created_at__date__lte=date_to_custom)
        elif date_range and date_range != 'all':
            # Preset date ranges - use centralized calculation
            date_range_info = get_preset_date_range(date_range, timezone_aware=True)
            if date_range_info.date_from and date_range_info.date_to:
                queryset = queryset.filter(
                    created_at__gte=date_range_info.date_from,
                    created_at__lt=date_range_info.date_to
                )
        # If date_range == 'all' or empty, no date filtering

        return queryset
    
    @classmethod
    def apply_date_filters_with_timezone(cls, queryset, filter_form):
        """
        Apply date filtering with explicit timezone handling for class-based views.
        
        Args:
            queryset: Django queryset to filter
            filter_form: Validated form with date filter data
            
        Returns:
            Filtered queryset
        """
        if not filter_form.is_valid():
            return queryset
            
        date_range = filter_form.cleaned_data.get('date_range')
        date_from_custom = filter_form.cleaned_data.get('date_from')
        date_to_custom = filter_form.cleaned_data.get('date_to')

        # Apply standardized date filtering with timezone awareness
        if date_range == 'custom':
            # Custom date range - use explicit date_from/date_to with timezone
            if date_from_custom:
                date_from_dt = timezone.make_aware(datetime.combine(date_from_custom, time.min))
                queryset = queryset.filter(created_at__gte=date_from_dt)
            if date_to_custom:
                date_to_dt = timezone.make_aware(datetime.combine(date_to_custom + timedelta(days=1), time.min))
                queryset = queryset.filter(created_at__lt=date_to_dt)
        elif date_range and date_range != 'all':
            # Preset date ranges - use centralized calculation
            date_range_info = get_preset_date_range(date_range, timezone_aware=True)
            if date_range_info.date_from and date_range_info.date_to:
                queryset = queryset.filter(
                    created_at__gte=date_range_info.date_from,
                    created_at__lt=date_range_info.date_to
                )
        # If date_range == 'all' or empty, no date filtering

        return queryset
    
    @classmethod
    def get_filter_dates(cls, period_type: str, custom_from: Optional[date] = None, 
                        custom_to: Optional[date] = None) -> Tuple[Optional[date], Optional[date]]:
        """
        Get date range for enquiry filtering - compatible with legacy DateRangeUtility.
        
        Args:
            period_type: '3months', '6months', '12months', 'all', or 'custom'
            custom_from: Custom start date (for 'custom' type)
            custom_to: Custom end date (for 'custom' type)
            
        Returns:
            Tuple of (date_from, date_to) or (None, None) for 'all'
        """
        if period_type == 'all':
            return None, None
        elif period_type == 'custom':
            return custom_from, custom_to
        
        # Use centralized date calculation for preset ranges
        if period_type in cls.PRESET_RANGES:
            date_range_info = get_preset_date_range(period_type, timezone_aware=False)
            if date_range_info.date_from and date_range_info.date_to:
                return date_range_info.date_from.date(), date_range_info.date_to.date()
        
        # Fallback to 12 months if invalid period_type
        date_range_info = get_preset_date_range('12months', timezone_aware=False)
        return date_range_info.date_from.date(), date_range_info.date_to.date()
