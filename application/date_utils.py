"""
Centralized date range calculation utilities for consistent date handling across all reports.

This module provides standardized date range calculations to ensure consistency
between different reports, views, and JavaScript frontend code.
"""

from datetime import datetime, date, time
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from typing import Tuple, Optional, NamedTuple, Dict, Any


class DateRange(NamedTuple):
    """Standard date range structure used across all reports."""
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    date_from_str: Optional[str]
    date_to_str: Optional[str]
    range_type: str
    months: Optional[int]


class DateRangeCalculator:
    """Centralized date range calculations for consistent behavior across all reports."""

    def __init__(self, timezone_aware: bool = True):
        self.timezone_aware = timezone_aware
        self.today = timezone.now().date() if timezone_aware else date.today()
        self.now = timezone.now() if timezone_aware else datetime.now()

    def calculate_preset_range(self, range_type: str) -> DateRange:
        """
        Calculate standardized date ranges for preset periods.

        Args:
            range_type: One of '3months', '6months', '12months', 'all'

        Returns:
            DateRange with consistent calculations using exact month arithmetic
        """
        if range_type == 'all':
            return DateRange(
                date_from=None,
                date_to=None,
                date_from_str='',
                date_to_str='',
                range_type='all',
                months=None
            )

        # Use exact month arithmetic for consistency
        months_map = {
            '3months': 3,
            '6months': 6,
            '12months': 12
        }

        months = months_map.get(range_type, 12)

        # Calculate using relativedelta for exact month arithmetic
        date_from_date = self.today - relativedelta(months=months)
        date_to_date = self.today

        # Convert to timezone-aware datetime objects
        if self.timezone_aware:
            date_from = timezone.make_aware(datetime.combine(date_from_date, time.min))
            date_to = timezone.make_aware(datetime.combine(date_to_date, time.max))
        else:
            date_from = datetime.combine(date_from_date, time.min)
            date_to = datetime.combine(date_to_date, time.max)

        return DateRange(
            date_from=date_from,
            date_to=date_to,
            date_from_str=date_from_date.strftime('%Y-%m-%d'),
            date_to_str=date_to_date.strftime('%Y-%m-%d'),
            range_type=range_type,
            months=months
        )

    def calculate_custom_range(self, date_from_str: Optional[str], date_to_str: Optional[str]) -> DateRange:
        """
        Calculate date range from custom date strings.

        Args:
            date_from_str: Date string in 'YYYY-MM-DD' format
            date_to_str: Date string in 'YYYY-MM-DD' format

        Returns:
            DateRange with parsed custom dates
        """
        date_from = None
        date_to = None

        # Parse date strings
        if date_from_str:
            try:
                date_from_date = datetime.strptime(date_from_str, '%Y-%m-%d').date()
                if self.timezone_aware:
                    date_from = timezone.make_aware(datetime.combine(date_from_date, time.min))
                else:
                    date_from = datetime.combine(date_from_date, time.min)
            except ValueError:
                date_from_str = ''

        if date_to_str:
            try:
                date_to_date = datetime.strptime(date_to_str, '%Y-%m-%d').date()
                if self.timezone_aware:
                    date_to = timezone.make_aware(datetime.combine(date_to_date, time.max))
                else:
                    date_to = datetime.combine(date_to_date, time.max)
            except ValueError:
                date_to_str = ''

        return DateRange(
            date_from=date_from,
            date_to=date_to,
            date_from_str=date_from_str or '',
            date_to_str=date_to_str or '',
            range_type='custom',
            months=None
        )

    def parse_request_dates(self, request, default_range: str = '12months') -> DateRange:
        """
        Parse date range from Django request parameters.

        Args:
            request: Django request object
            default_range: Default range type if none specified

        Returns:
            DateRange based on request parameters
        """
        range_type = request.GET.get('date_range', default_range)
        date_from_str = request.GET.get('date_from', '')
        date_to_str = request.GET.get('date_to', '')

        # If custom dates are provided but range is not explicitly custom,
        # check if they match any preset
        if (date_from_str or date_to_str) and range_type != 'custom':
            # Check if the provided dates match the selected preset
            preset_range = self.calculate_preset_range(range_type)
            if (date_from_str != preset_range.date_from_str or
                date_to_str != preset_range.date_to_str):
                range_type = 'custom'

        if range_type == 'custom':
            return self.calculate_custom_range(date_from_str, date_to_str)
        else:
            return self.calculate_preset_range(range_type)

    def get_javascript_dates(self) -> Dict[str, str]:
        """
        Get date strings for JavaScript to ensure client/server consistency.

        Returns:
            Dictionary with standardized date strings for JavaScript
        """
        ranges = {}
        for range_type in ['3months', '6months', '12months']:
            date_range = self.calculate_preset_range(range_type)
            ranges[range_type] = {
                'from': date_range.date_from_str,
                'to': date_range.date_to_str
            }

        ranges['today'] = self.today.strftime('%Y-%m-%d')
        return ranges


def get_date_range_calculator(timezone_aware: bool = True) -> DateRangeCalculator:
    """Factory function to create a date range calculator."""
    return DateRangeCalculator(timezone_aware=timezone_aware)


# Convenience functions for common use cases
def parse_request_date_range(request, default_range: str = '12months', timezone_aware: bool = True) -> DateRange:
    """Quick function to parse date range from request."""
    calculator = get_date_range_calculator(timezone_aware)
    return calculator.parse_request_dates(request, default_range)


def get_preset_date_range(range_type: str, timezone_aware: bool = True) -> DateRange:
    """Quick function to get a preset date range."""
    calculator = get_date_range_calculator(timezone_aware)
    return calculator.calculate_preset_range(range_type)


def get_javascript_date_constants(timezone_aware: bool = True) -> Dict[str, str]:
    """Quick function to get JavaScript date constants."""
    calculator = get_date_range_calculator(timezone_aware)
    return calculator.get_javascript_dates()


def get_date_range_description(date_range_info: DateRange, prefix: str = "for", include_dates: bool = False) -> str:
    """
    Generate human-readable descriptions for date ranges.

    Args:
        date_range_info: DateRange object with range information
        prefix: Prefix word ('for', 'over', 'during', etc.)
        include_dates: Whether to include actual dates in parentheses

    Returns:
        Human-readable string like "for the last 3 months" or "for all time"

    Examples:
        - "for the last 3 months"
        - "for the last 6 months"
        - "for the last 12 months"
        - "for all time"
        - "for custom date range"
        - "for the last 3 months (22/06/2024 - 23/09/2024)" (with include_dates=True)
    """
    range_type = date_range_info.range_type

    if range_type == 'all':
        description = f"{prefix} all time"
    elif range_type == 'custom':
        description = f"{prefix} custom date range"
    elif range_type in ['3months', '6months', '12months']:
        months = date_range_info.months
        description = f"{prefix} the last {months} months"
    else:
        description = f"{prefix} selected period"

    # Add actual dates if requested
    if include_dates and date_range_info.date_from_str and date_range_info.date_to_str:
        try:
            # Format dates as dd/mm/yyyy for display
            from_date = datetime.strptime(date_range_info.date_from_str, '%Y-%m-%d')
            to_date = datetime.strptime(date_range_info.date_to_str, '%Y-%m-%d')
            from_formatted = from_date.strftime('%d/%m/%Y')
            to_formatted = to_date.strftime('%d/%m/%Y')
            description += f" ({from_formatted} - {to_formatted})"
        except ValueError:
            pass

    return description


def get_date_range_subtitle(date_range_info: DateRange) -> str:
    """
    Generate subtitle text for reports showing the date range.

    Args:
        date_range_info: DateRange object with range information

    Returns:
        Subtitle string like "Showing data for the last 12 months"
    """
    return f"Showing data {get_date_range_description(date_range_info, 'for')}"


def get_page_title_with_date_range(base_title: str, date_range_info: DateRange) -> str:
    """
    Generate page titles with date range information formatted for headers.

    Args:
        base_title: Base title like "Job Workload" or "Performance Dashboard"
        date_range_info: DateRange object with range information

    Returns:
        Formatted title like "Job Workload (Last 6 Months)" or "Performance Dashboard (01/10/2024 - 31/10/2024)"

    Examples:
        - "Job Workload (Last 3 Months)"
        - "Performance Dashboard (All Time)"
        - "Section Workload (01/10/2024 - 31/10/2024)"
    """
    range_type = date_range_info.range_type

    if range_type == 'all':
        range_text = "All Time"
    elif range_type == 'custom':
        # Show actual dates for custom ranges
        if date_range_info.date_from_str and date_range_info.date_to_str:
            try:
                from_date = datetime.strptime(date_range_info.date_from_str, '%Y-%m-%d')
                to_date = datetime.strptime(date_range_info.date_to_str, '%Y-%m-%d')
                from_formatted = from_date.strftime('%d/%m/%Y')
                to_formatted = to_date.strftime('%d/%m/%Y')
                range_text = f"{from_formatted} - {to_formatted}"
            except ValueError:
                range_text = "Custom Range"
        else:
            range_text = "Custom Range"
    elif range_type in ['3months', '6months', '12months']:
        months = date_range_info.months
        range_text = f"Last {months} Months"
    else:
        range_text = "Selected Period"

    return f"{base_title} ({range_text})"


def build_enquiry_list_url(base_params: dict, date_range_info: DateRange) -> str:
    """
    Build a consistent enquiry list URL with proper date range parameters.

    Args:
        base_params: Dictionary of base parameters (e.g., {'member': '123', 'status': 'closed'})
        date_range_info: DateRange object with range information

    Returns:
        Query string for enquiry list URL (e.g., "?member=123&status=closed&date_range=12months")
    """
    from urllib.parse import urlencode

    # Start with base parameters
    params = base_params.copy()

    # Add date range parameter for consistency
    params['date_range'] = date_range_info.range_type

    # For preset ranges, we don't need to include specific dates
    # The enquiry list will calculate them consistently using the centralized system
    # This reduces URL length and improves maintainability

    # Only include specific dates for custom ranges
    if date_range_info.range_type == 'custom':
        if date_range_info.date_from_str:
            params['date_from'] = date_range_info.date_from_str
        if date_range_info.date_to_str:
            params['date_to'] = date_range_info.date_to_str

    return f"?{urlencode(params)}"