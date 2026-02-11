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
Tests for business day calculations.
"""

import pytest
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.test import TestCase

from application.utils import calculate_business_days, calculate_working_days_due_date


@pytest.mark.django_db
class TestBusinessDayCalculations:
    """Test business day calculation utilities."""

    def test_calculate_business_days_basic(self):
        """Test basic business day calculation."""
        # Monday to Friday (5 business days)
        start_date = date(2024, 1, 1)  # Monday
        end_date = date(2024, 1, 5)  # Friday

        result = calculate_business_days(start_date, end_date)
        assert result == 4  # 4 business days between (not including start day)

    def test_calculate_business_days_with_weekend(self):
        """Test business day calculation spanning weekends."""
        # Friday to Monday (1 business day, skipping weekend)
        start_date = date(2024, 1, 5)  # Friday
        end_date = date(2024, 1, 8)  # Monday

        result = calculate_business_days(start_date, end_date)
        assert result == 1  # Only Monday counts as business day

    def test_calculate_business_days_two_weeks(self):
        """Test business day calculation for exactly 2 weeks."""
        # Test case: January 1, 2024 (Monday) to January 15, 2024 (Monday)
        # This spans exactly 2 weeks (14 calendar days)
        start_date = date(2024, 1, 1)  # Monday, January 1, 2024
        end_date = date(2024, 1, 15)  # Monday, January 15, 2024

        result = calculate_business_days(start_date, end_date)

        # Manual calculation:
        # Week 1: Jan 2 (Tue), 3 (Wed), 4 (Thu), 5 (Fri) = 4 days
        # Week 2: Jan 8 (Mon), 9 (Tue), 10 (Wed), 11 (Thu), 12 (Fri) = 5 days
        # Week 3: Jan 15 (Mon) = 1 day
        # Total: 4 + 5 + 1 = 10 business days
        assert result == 10

    def test_calculate_business_days_different_two_week_span(self):
        """Test business day calculation for another 2-week span."""
        # Test case: January 3, 2024 (Wednesday) to January 17, 2024 (Wednesday)
        start_date = date(2024, 1, 3)  # Wednesday
        end_date = date(2024, 1, 17)  # Wednesday

        result = calculate_business_days(start_date, end_date)

        # Manual calculation (January 3 is Wednesday):
        # Jan 4 (Thu), 5 (Fri) = 2 days
        # Jan 8 (Mon), 9 (Tue), 10 (Wed), 11 (Thu), 12 (Fri) = 5 days
        # Jan 15 (Mon), 16 (Tue), 17 (Wed) = 3 days
        # Total: 2 + 5 + 3 = 10 business days
        assert result == 10

    def test_calculate_business_days_with_datetime_objects(self):
        """Test business day calculation with datetime objects."""
        start_datetime = datetime(2024, 1, 1, 9, 0, 0)  # Monday 9 AM
        end_datetime = datetime(2024, 1, 15, 17, 0, 0)  # Monday 5 PM (2 weeks later)

        result = calculate_business_days(start_datetime, end_datetime)
        assert result == 10  # Same as the date-only test

    def test_calculate_business_days_same_day(self):
        """Test business day calculation for same day."""
        start_date = date(2024, 1, 1)  # Monday
        end_date = date(2024, 1, 1)  # Same Monday

        result = calculate_business_days(start_date, end_date)
        assert result == 0  # No days between same date

    def test_calculate_business_days_weekend_only(self):
        """Test business day calculation for weekend span."""
        start_date = date(2024, 1, 6)  # Saturday
        end_date = date(2024, 1, 7)  # Sunday

        result = calculate_business_days(start_date, end_date)
        assert result == 0  # No business days in weekend

    def test_calculate_business_days_invalid_input(self):
        """Test business day calculation with invalid input."""
        result1 = calculate_business_days(None, date(2024, 1, 1))
        assert result1 is None

        result2 = calculate_business_days(date(2024, 1, 1), None)
        assert result2 is None

        result3 = calculate_business_days(None, None)
        assert result3 is None

    def test_calculate_working_days_due_date_basic(self):
        """Test working days due date calculation."""
        start_date = date(2024, 1, 1)  # Monday
        business_days = 5

        result = calculate_working_days_due_date(start_date, business_days)
        expected = date(2024, 1, 8)  # Monday next week
        assert result == expected

    def test_calculate_working_days_due_date_from_friday(self):
        """Test working days due date calculation starting from Friday."""
        start_date = date(2024, 1, 5)  # Friday
        business_days = 3

        result = calculate_working_days_due_date(start_date, business_days)
        expected = date(2024, 1, 10)  # Wednesday next week (skipping weekend)
        assert result == expected

    def test_calculate_working_days_due_date_ten_days(self):
        """Test working days due date calculation for 10 business days (2 weeks)."""
        start_date = date(2024, 1, 1)  # Monday
        business_days = 10

        result = calculate_working_days_due_date(start_date, business_days)
        expected = date(2024, 1, 15)  # Monday, 2 weeks later
        assert result == expected

    def test_calculate_working_days_due_date_with_datetime(self):
        """Test working days due date calculation with datetime input."""
        start_datetime = datetime(2024, 1, 1, 14, 30, 0)  # Monday 2:30 PM
        business_days = 5

        result = calculate_working_days_due_date(start_datetime, business_days)
        expected = date(2024, 1, 8)  # Monday next week
        assert result == expected

    def test_calculate_working_days_due_date_invalid_input(self):
        """Test working days due date calculation with invalid input."""
        result1 = calculate_working_days_due_date(None, 5)
        assert result1 is None

        result2 = calculate_working_days_due_date(date(2024, 1, 1), None)
        assert result2 is None

        result3 = calculate_working_days_due_date(None, None)
        assert result3 is None

    def test_business_days_real_world_scenario(self):
        """Test a real-world scenario: enquiry created on Wednesday, due in 5 business days."""
        # Enquiry created on Wednesday, January 3, 2024
        created_date = date(2024, 1, 3)  # Wednesday

        # Due date should be 5 business days later
        due_date = calculate_working_days_due_date(created_date, 5)

        # Expected: Thu (4th), Fri (5th), Mon (8th), Tue (9th), Wed (10th)
        expected_due = date(2024, 1, 10)  # Wednesday next week
        assert due_date == expected_due

        # Verify the calculation by counting back
        days_between = calculate_business_days(created_date, due_date)
        assert days_between == 5

    def test_business_days_across_month_boundary(self):
        """Test business day calculation across month boundaries."""
        # January 29, 2024 (Monday) to February 9, 2024 (Friday)
        start_date = date(2024, 1, 29)  # Monday
        end_date = date(2024, 2, 9)  # Friday

        result = calculate_business_days(start_date, end_date)

        # Manual count:
        # Jan: 30 (Tue), 31 (Wed) = 2 days
        # Feb: 1 (Thu), 2 (Fri), 5 (Mon), 6 (Tue), 7 (Wed), 8 (Thu), 9 (Fri) = 7 days
        # Total: 2 + 7 = 9 business days
        assert result == 9

    def test_enquiry_sla_calculation(self):
        """Test SLA calculation scenario - 5 business day target."""
        # Enquiry created Monday morning
        created = datetime(2024, 1, 1, 9, 0, 0)  # Monday 9 AM

        # Calculate due date (5 business days later)
        due_date = calculate_working_days_due_date(created, 5)
        assert due_date == date(2024, 1, 8)  # Monday next week

        # Test different closure scenarios
        closed_on_time = datetime(2024, 1, 8, 16, 0, 0)  # Monday 4 PM (on time)
        closed_late = datetime(2024, 1, 10, 10, 0, 0)  # Wednesday (2 days late)

        # Calculate actual business days to close
        days_on_time = calculate_business_days(created, closed_on_time)
        days_late = calculate_business_days(created, closed_late)

        assert days_on_time == 5  # Exactly on SLA
        assert days_late == 7  # 2 business days over SLA

        # SLA met if <= 5 business days
        assert days_on_time <= 5  # SLA met
        assert days_late > 5  # SLA missed
