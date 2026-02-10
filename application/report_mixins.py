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
Report mixins for the Members Enquiries System.

This module provides reusable mixins for report views,
promoting code reuse and consistent reporting patterns.
"""

from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone
from django.views.generic import TemplateView

from .models import Enquiry, Member, Section, Ward


class BaseReportMixin(LoginRequiredMixin):
    """Base mixin for all report views."""
    
    def get_date_range_from_request(self, default_months=12):
        """Get date range from request parameters."""
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        months = int(self.request.GET.get('months', default_months))
        
        # If no specific dates provided, use months parameter
        if not start_date and not end_date:
            date_from = timezone.now() - timedelta(days=months * 30)
            return date_from, None, months
        
        return start_date, end_date, months
    
    def get_common_filters(self):
        """Get common filter parameters from request."""
        return {
            'member_id': self.request.GET.get('member'),
            'section_id': self.request.GET.get('section'),
            'ward_id': self.request.GET.get('ward'),
        }


class ResponseTimeReportMixin(BaseReportMixin):
    """Mixin for response time related reports."""
    
    def get_response_time_queryset(self):
        """Get base queryset for response time calculations."""
        start_date, end_date, months = self.get_date_range_from_request()
        filters = self.get_common_filters()
        
        # Base queryset for closed enquiries
        enquiries = Enquiry.objects.filter(status='closed', closed_at__isnull=False)
        
        # Apply date filters
        if start_date:
            enquiries = enquiries.filter(created_at__date__gte=start_date)
        if end_date:
            enquiries = enquiries.filter(created_at__date__lte=end_date)
        if not start_date and not end_date:
            date_from = timezone.now() - timedelta(days=months * 30)
            enquiries = enquiries.filter(created_at__gte=date_from)
        
        # Apply other filters
        if filters['member_id']:
            enquiries = enquiries.filter(member_id=filters['member_id'])
        if filters['section_id']:
            enquiries = enquiries.filter(section_id=filters['section_id'])
        
        # Calculate response times
        enquiries = enquiries.annotate(
            response_time_days=ExpressionWrapper(
                F('closed_at') - F('created_at'),
                output_field=DurationField()
            )
        ).select_related('member', 'section__department', 'admin__user')
        
        return enquiries, {'start_date': start_date, 'end_date': end_date, 'months': months}


class OverdueReportMixin(BaseReportMixin):
    """Mixin for overdue enquiry reports."""
    
    def get_overdue_queryset(self, threshold_days=5):
        """Get queryset of overdue enquiries using business days calculation."""
        from .utils import calculate_business_days
        filters = self.get_common_filters()

        # Get all open enquiries (we'll filter by business days logic)
        enquiries = Enquiry.objects.filter(
            status__in=['new', 'open']
        ).select_related('member', 'section__department', 'admin__user')

        # Apply filters
        if filters['member_id']:
            enquiries = enquiries.filter(member_id=filters['member_id'])
        if filters['section_id']:
            enquiries = enquiries.filter(section_id=filters['section_id'])

        # Filter by business days overdue
        overdue_enquiries = []
        for enquiry in enquiries:
            business_days_since_created = calculate_business_days(enquiry.created_at, timezone.now())
            if business_days_since_created is not None and business_days_since_created > threshold_days:
                overdue_enquiries.append(enquiry)

        return overdue_enquiries, threshold_days


class CountReportMixin(BaseReportMixin):
    """Mixin for count-based reports (per member, section, ward)."""
    
    def get_count_data(self, model_class, filter_field, months=12):
        """
        Get count data for a specific model.
        
        Args:
            model_class: Model to count (Member, Section, Ward)
            filter_field: Field to filter enquiries by
            months: Number of months to look back
        """
        date_from = timezone.now() - timedelta(days=months * 30)
        
        objects = model_class.objects.filter(
            **{f'{filter_field}__created_at__gte': date_from}
        ).annotate(
            enquiry_count=Count(filter_field)
        ).order_by('-enquiry_count')
        
        if model_class == Section:
            objects = objects.select_related('department')
        
        return objects, date_from, months


class MonthlyReportMixin(BaseReportMixin):
    """Mixin for monthly SLA performance reports."""
    
    def get_monthly_data(self, selected_month=None):
        """Get SLA performance data for a specific month."""
        if not selected_month:
            selected_month = timezone.now().strftime('%Y-%m')
        
        try:
            year, month = map(int, selected_month.split('-'))
            selected_date = datetime(year, month, 1)
        except (ValueError, TypeError):
            selected_date = timezone.now().replace(day=1)
            selected_month = selected_date.strftime('%Y-%m')
        
        # Calculate month range
        month_start = selected_date.replace(day=1)
        if month == 12:
            month_end = month_start.replace(year=year + 1, month=1)
        else:
            month_end = month_start.replace(month=month + 1)
        
        # Generate list of months for dropdown (last 24 months)
        months_list = []
        current_date = timezone.now().replace(day=1)
        for i in range(24):
            month_date = current_date - timedelta(days=i * 30)
            month_date = month_date.replace(day=1)
            months_list.append(month_date)
        
        return {
            'selected_month': selected_month,
            'selected_date': selected_date,
            'month_start': month_start,
            'month_end': month_end,
            'months_list': months_list
        }
    
    def get_sla_sections(self, month_start, month_end, sla_days=5):
        """Get sections with SLA performance data using business days calculation."""
        from .utils import calculate_business_days

        # Get all enquiries for the month
        month_enquiries = Enquiry.objects.filter(
            created_at__gte=month_start,
            created_at__lt=month_end
        ).select_related('section')

        # Calculate SLA performance for each section
        section_data = {}

        for enquiry in month_enquiries:
            section_id = enquiry.section.id if enquiry.section else None
            section_name = enquiry.section.name if enquiry.section else 'Unassigned'

            if section_id not in section_data:
                section_data[section_id] = {
                    'id': section_id,
                    'name': section_name,
                    'section': enquiry.section,
                    'enquiries_within_sla': 0,
                    'enquiries_outside_sla': 0,
                    'enquiries_open': 0
                }

            if enquiry.status == 'closed' and enquiry.closed_at:
                # Calculate business days to close
                business_days_to_close = calculate_business_days(enquiry.created_at, enquiry.closed_at)
                if business_days_to_close is not None and business_days_to_close <= sla_days:
                    section_data[section_id]['enquiries_within_sla'] += 1
                else:
                    section_data[section_id]['enquiries_outside_sla'] += 1
            elif enquiry.status in ['new', 'open']:
                section_data[section_id]['enquiries_open'] += 1

        # Convert to list and filter out sections with no enquiries
        sections = []
        for data in section_data.values():
            if (data['enquiries_within_sla'] > 0 or
                data['enquiries_outside_sla'] > 0 or
                data['enquiries_open'] > 0):
                sections.append(data)

        # Sort by section name
        sections.sort(key=lambda x: x['name'] or 'ZZZ')

        return sections


class EnquiryListReportMixin(BaseReportMixin):
    """Mixin for views that show filtered lists of enquiries."""
    
    def get_enquiry_list(self, **filter_kwargs):
        """Get a filtered list of enquiries."""
        enquiries = Enquiry.objects.filter(**filter_kwargs).select_related(
            'member__user', 'member__ward', 'admin__user', 'section', 'contact'
        ).order_by('-created_at')
        
        return enquiries