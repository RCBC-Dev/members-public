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
Date calculation utilities for enquiry resolution times.

This module provides flexible date calculation methods that can be easily
modified to suit different business requirements.
"""

from datetime import timedelta
from typing import Optional, Union
import datetime


def calculate_resolution_days(
    start_date: Union[datetime.datetime, datetime.date],
    end_date: Union[datetime.datetime, datetime.date],
    method: str = "business",
) -> Optional[int]:
    """
    Calculate resolution time between two dates using different methods.

    Args:
        start_date: When the enquiry was created
        end_date: When the enquiry was closed
        method: Calculation method ('calendar', 'business', 'working')

    Returns:
        Number of days or None if calculation fails
    """
    if not start_date or not end_date:
        return None

    try:
        # Convert to date objects if they're datetime
        if hasattr(start_date, "date"):
            start_date = start_date.date()
        if hasattr(end_date, "date"):
            end_date = end_date.date()

        if method == "calendar":
            return (end_date - start_date).days
        elif method == "business":
            return calculate_business_days(start_date, end_date)
        elif method == "working":
            return calculate_working_days(start_date, end_date)
        else:
            return (end_date - start_date).days

    except (TypeError, AttributeError):
        return None


def calculate_business_days(start_date: datetime.date, end_date: datetime.date) -> int:
    """
    Calculate business days (excluding weekends).

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Number of business days
    """
    business_days = 0
    current_date = start_date

    while current_date < end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            business_days += 1
        current_date += timedelta(days=1)

    return business_days


def calculate_working_days(start_date: datetime.date, end_date: datetime.date) -> int:
    """
    Calculate working days (excluding weekends and holidays).

    This is where you can add holiday exclusions, custom working days, etc.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Number of working days
    """
    # Start with business days
    working_days = calculate_business_days(start_date, end_date)

    # Holiday exclusions can be added here if needed, for example:
    # - UK bank holidays (via python-holidays library)
    # - Council-specific closure days
    # - Custom holiday calendar

    return working_days


def get_resolution_time_color(days: int, method: str = "business") -> str:
    """
    Get CSS color class based on resolution time.

    Args:
        days: Number of days to resolve
        method: Calculation method used

    Returns:
        CSS class name for color coding
    """
    if method == "business":
        # Business days thresholds
        if days <= 1:
            return "text-success"  # Green - excellent
        elif days <= 5:
            return "text-warning"  # Yellow - good (1 week)
        else:
            return "text-danger"  # Red - needs attention
    else:
        # Calendar days thresholds
        if days <= 1:
            return "text-success"  # Green - excellent
        elif days <= 7:
            return "text-warning"  # Yellow - good (1 week)
        else:
            return "text-danger"  # Red - needs attention


def format_resolution_time(days: int, method: str = "business") -> str:
    """
    Format resolution time for display.

    Args:
        days: Number of days
        method: Calculation method used

    Returns:
        Formatted string for display
    """
    if method == "business":
        unit = "business day" if days == 1 else "business days"
    else:
        unit = "day" if days == 1 else "days"

    return f"{days} {unit}"


# Configuration constants - easily modifiable
RESOLUTION_TIME_METHOD = "business"  # 'calendar', 'business', or 'working'

# Thresholds for color coding (in days)
EXCELLENT_THRESHOLD = 1
GOOD_THRESHOLD = 5 if RESOLUTION_TIME_METHOD == "business" else 7

# Future enhancement ideas:
# - Add support for different time zones
# - Add support for half-day calculations
# - Add support for hour-based calculations
# - Add integration with external holiday APIs
# - Add support for different working week patterns (e.g., 4-day weeks)
