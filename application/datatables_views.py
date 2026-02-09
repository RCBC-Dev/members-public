"""
DataTables server-side processing views for the Members Enquiries System.

This module provides AJAX endpoints for DataTables server-side processing,
dramatically improving performance for large datasets.
"""

import json
import re
from datetime import date, datetime, time as dt_time, timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt

from .class_views import EnquiryFilterMixin
from .forms import EnquiryFilterForm
from .models import Enquiry
from .search_service import EnquirySearchService
# Template tags not needed for server-side processing


class DataTablesServerSide:
    """Handle DataTables server-side processing for enquiries."""
    
    def __init__(self, request, request_data=None):
        self.request = request
        if request_data is None:
            request_data = request.GET
        
        self.draw = int(request_data.get('draw', 1))
        self.start = max(0, int(request_data.get('start', 0)))  # Ensure non-negative
        self.length = int(request_data.get('length', 10))
        
        # Handle "All" option (-1) by setting a reasonable maximum
        if self.length == -1:
            self.length = 10000  # Large but manageable number
        
        # DataTables search
        self.search_value = request_data.get('search[value]', '').strip()
        
        # DataTables ordering
        self.order_column = int(request_data.get('order[0][column]', 9))  # Default to Created column
        self.order_dir = request_data.get('order[0][dir]', 'desc')
        
        # Column mapping for ordering
        self.columns = [
            'reference',         # 0
            'title',            # 1
            'member__first_name',  # 2
            'section__name',    # 3
            'job_type__name',   # 4
            'service_type',     # 5 - Service Type
            'contact__name',    # 6
            'status',           # 7
            'admin__user__first_name',  # 8
            'created_at',       # 9
            'updated_at',       # 10
            'due_date',         # 11 - Due Date (sortable database field)
            None,               # 12 - Overdue Days (calculated, not sortable)
            'closed_at',        # 13
            None,               # 14 - Resolution Time (calculated)
            None,               # 15 - Actions (not sortable)
        ]
    
    def get_base_queryset(self, filter_mixin, filter_form):
        """Get the base queryset with filters applied."""
        # Check if we have search terms (either from DataTables or form)
        form_search = ''
        if hasattr(filter_form, 'cleaned_data') and filter_form.cleaned_data:
            form_search = filter_form.cleaned_data.get('search', '')
        
        # Start with optimized queryset
        if not self.search_value and not form_search:
            queryset = Enquiry.objects.select_related(
                'member', 'admin__user', 'section', 'job_type', 'contact'
            ).defer('description')
        else:
            queryset = Enquiry.objects.select_related(
                'member', 'admin__user', 'section', 'job_type', 'contact'
            )
        
        # Apply filters from the filter form
        queryset = filter_mixin.apply_filters(queryset, filter_form)
        
        return queryset
    
    def apply_datatables_search(self, queryset):
        """Apply DataTables global search using centralized search service."""
        return EnquirySearchService.apply_search(queryset, self.search_value)
    
    def apply_ordering(self, queryset):
        """Apply DataTables ordering."""
        if self.order_column < len(self.columns) and self.columns[self.order_column]:
            order_field = self.columns[self.order_column]
            if self.order_dir == 'desc':
                order_field = f'-{order_field}'
            queryset = queryset.order_by(order_field)
        else:
            # Default ordering
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def format_enquiry_row(self, enquiry, today, current_filters=None):
        """Format a single enquiry row for DataTables."""
        # Build filter URLs that preserve current filters
        def build_filter_url(**kwargs):
            base_url = reverse('application:enquiry_list')
            # Start with current filters if available
            merged_filters = {}
            if current_filters:
                merged_filters.update(current_filters)
            # Add/override with new filter parameters
            merged_filters.update(kwargs)
            return f"{base_url}?{urlencode(merged_filters)}"
        
        # Status badge
        if enquiry.status == 'new' or enquiry.status == 'open':
            status_class = 'bg-primary'
            status_text = 'Open' if enquiry.status == 'new' else enquiry.get_status_display()
        elif enquiry.status == 'closed':
            status_class = 'bg-success'
            status_text = enquiry.get_status_display()
        else:
            status_class = 'bg-secondary'
            status_text = enquiry.get_status_display()
        
        # Resolution time - calculate manually for now
        from application.utils import calculate_business_days
        
        resolution_time_html = '-'
        if enquiry.status == 'closed' and enquiry.closed_at:
            business_days = calculate_business_days(enquiry.created_at, enquiry.closed_at)
            if business_days is not None:
                # Simple color coding
                if business_days <= 5:
                    color_class = 'text-success'
                elif business_days <= 10:
                    color_class = 'text-warning'
                else:
                    color_class = 'text-danger'
                
                resolution_time_html = f'<span class="{color_class}">{business_days}</span>'
        
        # Actions buttons - using AJAX close functionality like the dashboard
        actions_html = f'''
        <div class="btn-group btn-group-sm" role="group">
            <a href="{reverse('application:enquiry_detail', args=[enquiry.id])}" class="btn btn-outline-primary" title="View enquiry details">
                <i class="bi bi-eye"></i> View
            </a>
        '''
        
        if enquiry.status != 'closed':
            actions_html += f'''
            <a href="{reverse('application:enquiry_edit', args=[enquiry.id])}" class="btn btn-outline-secondary" title="Edit this enquiry">
                <i class="bi bi-pencil"></i> Edit
            </a>
            <button type="button" class="btn btn-outline-danger" 
                    data-bs-toggle="modal" 
                    data-bs-target="#enquiryActionModal"
                    data-enquiry-id="{enquiry.id}" 
                    data-enquiry-ref="{escape(enquiry.reference or 'No Ref')}"
                    data-enquiry-title="{escape(enquiry.title)}"
                    data-action="close"
                    title="Close this enquiry">
                <i class="bi bi-x-circle"></i> Close
            </button>
            '''
        else:
            actions_html += f'''
            <button type="button" class="btn btn-outline-success" 
                    data-bs-toggle="modal" 
                    data-bs-target="#enquiryActionModal"
                    data-enquiry-id="{enquiry.id}" 
                    data-enquiry-ref="{escape(enquiry.reference or 'No Ref')}"
                    data-enquiry-title="{escape(enquiry.title)}"
                    data-action="reopen"
                    title="Re-open this enquiry">
                <i class="bi bi-arrow-clockwise"></i> Re-open
            </button>
            '''
        
        actions_html += '</div>'
        
        # Check if overdue - handle datetime vs date comparison
        due_date = enquiry.due_date.date() if hasattr(enquiry.due_date, 'date') else enquiry.due_date
        is_overdue = due_date < today and enquiry.status != 'closed'
        due_date_class = 'text-danger fw-bold' if is_overdue else ''
        
        # Calculate overdue days for open enquiries
        overdue_days_html = '-'
        if enquiry.status != 'closed' and is_overdue:
            from application.utils import calculate_business_days
            overdue_business_days = calculate_business_days(due_date, today)
            if overdue_business_days and overdue_business_days > 0:
                if overdue_business_days <= 2:
                    # 1-2 days overdue: Yellow warning
                    color_class = 'text-warning fw-bold'
                elif overdue_business_days <= 5:
                    # 3-5 days overdue: Red urgent
                    color_class = 'text-danger fw-bold'
                else:
                    # 6+ days overdue: White text on red background (critical)
                    color_class = 'fw-bold text-white bg-danger px-2 py-1 rounded'
                overdue_days_html = f'<span class="{color_class}" title="{overdue_business_days} business days overdue">{overdue_business_days}</span>'
        
        # Build row data
        row_data = [
            f'<a href="{reverse("application:enquiry_detail", args=[enquiry.id])}" class="text-decoration-none fw-bold">{escape(enquiry.reference or "No Ref")}</a>',  # 0
            escape(enquiry.title[:50] + ('...' if len(enquiry.title) > 50 else '')),  # 1
            f'<a href="{build_filter_url(member=enquiry.member.id)}" class="text-decoration-none" title="Filter by this member">{escape(enquiry.member.full_name)}</a>',  # 2
            f'<a href="{build_filter_url(section=enquiry.section.id)}" class="text-decoration-none" title="Filter by this section">{escape(enquiry.section.name)}</a>' if enquiry.section else 'Not assigned',  # 3
            f'<a href="{build_filter_url(job_type=enquiry.job_type.id)}" class="text-decoration-none" title="Filter by this job type">{escape(enquiry.job_type.name)}</a>' if enquiry.job_type else 'Not assigned',  # 4
            f'<a href="{build_filter_url(service_type=enquiry.service_type)}" class="text-decoration-none" title="Filter by this service type">{escape(enquiry.get_service_type_display())}</a>' if enquiry.service_type else 'Not set',  # 5 - Service Type
            f'<a href="{build_filter_url(contact=enquiry.contact.id)}" class="text-decoration-none" title="Filter by this contact">{escape(enquiry.contact.name)}</a>' if enquiry.contact else 'Not assigned',  # 6
            f'<span class="badge {status_class}">{escape(status_text)}</span>',  # 7
            f'<a href="{build_filter_url(admin=enquiry.admin.id)}" class="text-decoration-none" title="Filter by this admin">{escape(enquiry.admin.user.get_full_name() or enquiry.admin.user.username)}</a>' if enquiry.admin and enquiry.admin.user else 'Unassigned',  # 8
            (enquiry.created_at.date() if hasattr(enquiry.created_at, 'date') else enquiry.created_at).strftime('%Y-%m-%d'),  # 9
            (enquiry.updated_at.date() if hasattr(enquiry.updated_at, 'date') else enquiry.updated_at).strftime('%Y-%m-%d'),  # 10
            f'<span class="{due_date_class}">{due_date.strftime("%Y-%m-%d")}</span>',  # 11
            overdue_days_html,  # 12
            (enquiry.closed_at.date() if hasattr(enquiry.closed_at, 'date') else enquiry.closed_at).strftime('%Y-%m-%d') if enquiry.status == 'closed' and enquiry.closed_at else '-',  # 13
            resolution_time_html,  # 14
            actions_html  # 15
        ]
        
        # Add row attributes for styling (DataTables will use DT_RowClass)
        row_attrs = {
            'DT_RowId': f'enquiry-{enquiry.id}',
            'DT_RowData': {'enquiry-id': enquiry.id}
        }
        
        if is_overdue:
            row_attrs['DT_RowClass'] = 'table-warning'
        
        return {
            'data': row_data,
            **row_attrs
        }
    
    def get_response_data(self, filter_mixin, filter_form):
        """Get the complete DataTables response data."""
        # Get base queryset with filters
        queryset = self.get_base_queryset(filter_mixin, filter_form)

        # Apply DataTables search
        queryset = self.apply_datatables_search(queryset)

        # Get total count before pagination
        records_total = Enquiry.objects.count()
        records_filtered = queryset.count()

        # Apply ordering
        queryset = self.apply_ordering(queryset)

        # Apply pagination
        paginated_queryset = queryset[self.start:self.start + self.length]

        # Extract current filters from filter_form for contextual linking
        current_filters = {}
        if hasattr(filter_form, 'cleaned_data') and filter_form.cleaned_data:
            for field_name, value in filter_form.cleaned_data.items():
                if value and value != '' and value != 'all':  # Only include non-empty, non-default filters
                    # Convert model instances to their IDs for URL parameters
                    if hasattr(value, 'id'):
                        current_filters[field_name] = str(value.id)
                    elif isinstance(value, bool):
                        if value:  # Only include True boolean values (like overdue_only)
                            current_filters[field_name] = 'on'
                    else:
                        current_filters[field_name] = str(value)
        
        # Format data for DataTables
        today = timezone.now().date()
        data = []
        for enquiry in paginated_queryset:
            row_data = self.format_enquiry_row(enquiry, today, current_filters)
            data.append(row_data['data'])  # DataTables expects just the data array

        # Generate dynamic title based on current filters
        from .services import EnquiryFilterService
        dynamic_title = EnquiryFilterService.generate_dynamic_title(filter_form)

        return {
            'draw': self.draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data,
            'dynamicTitle': dynamic_title  # Add dynamic title to response
        }


@login_required
@csrf_exempt  # DataTables sends POST requests
def enquiry_list_datatables(request):
    """
    AJAX endpoint for DataTables server-side processing.
    
    This handles pagination, searching, and sorting on the server side,
    dramatically improving performance for large datasets.
    """
    try:
        # DataTables can send GET or POST requests - handle both
        request_data = request.POST if request.method == 'POST' else request.GET
        
        # Initialize filter form with current filters
        filter_form = EnquiryFilterForm(request_data)
        
        # IMPORTANT: Must call is_valid() to populate cleaned_data
        filter_form.is_valid()
        
        # Initialize filter mixin
        filter_mixin = EnquiryFilterMixin()
        
        # Initialize DataTables handler with request data
        dt = DataTablesServerSide(request, request_data)
        
        # Get response data
        response_data = dt.get_response_data(filter_mixin, filter_form)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        # Return error response for debugging
        import traceback
        import logging
        
        logger = logging.getLogger(__name__)
        logger.error(f"DataTables AJAX error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'draw': request_data.get('draw', 1),
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        }, status=500)