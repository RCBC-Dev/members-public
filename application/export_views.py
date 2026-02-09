"""
Server-side export views for the Members Enquiries System.

These views handle exporting filtered enquiry data in various formats,
supporting the full dataset regardless of pagination.
"""

import csv
import io
import json
from datetime import datetime
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from .class_views import EnquiryFilterMixin
from .forms import EnquiryFilterForm
from .models import Enquiry
from .services import EnquiryFilterService
from .date_range_service import DateRangeService
from .search_service import EnquirySearchService


class ExportDataProcessor:
    """Process enquiry data for export in various formats."""
    
    def __init__(self, request_data, user):
        self.request_data = request_data
        self.user = user
        self.filter_mixin = EnquiryFilterMixin()
        
    def get_filtered_queryset(self):
        """Get the complete filtered queryset (not paginated)."""
        # Initialize filter form
        filter_form = EnquiryFilterForm(self.request_data)
        filter_form.is_valid()
        
        # Start with optimized queryset for export
        queryset = Enquiry.objects.select_related(
            'member', 'admin__user', 'section', 'job_type', 'contact'
        ).order_by('-created_at')
        
        # Apply filters using centralized service
        queryset = DateRangeService.apply_date_filters(queryset, filter_form)

        # Apply other filters (non-date filters)
        if filter_form.is_valid():
            # Status filter
            status = filter_form.cleaned_data.get('status')
            if status:
                if status == 'open':
                    queryset = queryset.filter(status__in=['new', 'open'])
                else:
                    queryset = queryset.filter(status=status)

            # Other filters
            if filter_form.cleaned_data.get('member'):
                queryset = queryset.filter(member=filter_form.cleaned_data['member'])
            if filter_form.cleaned_data.get('admin'):
                queryset = queryset.filter(admin=filter_form.cleaned_data['admin'])
            if filter_form.cleaned_data.get('section'):
                queryset = queryset.filter(section=filter_form.cleaned_data['section'])
            if filter_form.cleaned_data.get('job_type'):
                queryset = queryset.filter(job_type=filter_form.cleaned_data['job_type'])
            if filter_form.cleaned_data.get('contact'):
                queryset = queryset.filter(contact=filter_form.cleaned_data['contact'])
            if filter_form.cleaned_data.get('ward'):
                queryset = queryset.filter(member__ward=filter_form.cleaned_data['ward'])
        
        # Apply DataTables search if present
        search_value = self.request_data.get('search[value]', '').strip()
        if search_value:
            queryset = self._apply_search(queryset, search_value)
        
        return queryset, filter_form
    
    def _apply_search(self, queryset, search_value):
        """Apply search to queryset using centralized search service."""
        return EnquirySearchService.apply_search(queryset, search_value)
    
    def get_export_data(self):
        """Get data formatted for export."""
        queryset, filter_form = self.get_filtered_queryset()
        
        # Generate dynamic title
        dynamic_title = EnquiryFilterService.generate_dynamic_title(filter_form)
        
        # Convert queryset to export format
        today = timezone.now().date()
        export_data = []
        
        for enquiry in queryset:
            # Handle date formatting
            created_date = enquiry.created_at.date() if hasattr(enquiry.created_at, 'date') else enquiry.created_at
            updated_date = enquiry.updated_at.date() if hasattr(enquiry.updated_at, 'date') else enquiry.updated_at
            due_date = enquiry.due_date.date() if hasattr(enquiry.due_date, 'date') else enquiry.due_date
            closed_date = None
            if enquiry.status == 'closed' and enquiry.closed_at:
                closed_date = enquiry.closed_at.date() if hasattr(enquiry.closed_at, 'date') else enquiry.closed_at

            # Calculate overdue days for open enquiries
            overdue_days = '-'
            is_overdue = due_date < today and enquiry.status != 'closed'
            if enquiry.status != 'closed' and is_overdue:
                from application.utils import calculate_business_days
                overdue_business_days = calculate_business_days(due_date, today)
                if overdue_business_days and overdue_business_days > 0:
                    overdue_days = str(overdue_business_days)

            # Calculate resolution time
            resolution_time = '-'
            if enquiry.status == 'closed' and enquiry.closed_at:
                from application.utils import calculate_business_days
                business_days = calculate_business_days(enquiry.created_at, enquiry.closed_at)
                if business_days is not None:
                    resolution_time = str(business_days)

            # Status display
            status_display = 'Open' if enquiry.status == 'new' else enquiry.get_status_display()

            export_data.append({
                'reference': enquiry.reference or 'No Ref',
                'title': enquiry.title,
                'member': enquiry.member.full_name,
                'section': enquiry.section.name if enquiry.section else 'Not assigned',
                'job_type': enquiry.job_type.name if enquiry.job_type else 'Not assigned',
                'contact': enquiry.contact.name if enquiry.contact else 'Not assigned',
                'status': status_display,
                'admin': enquiry.admin.user.get_full_name() or enquiry.admin.user.username if enquiry.admin and enquiry.admin.user else 'Unassigned',
                'created': created_date.strftime('%d/%m/%Y'),  # DD/MM/YYYY format for exports
                'updated': updated_date.strftime('%d/%m/%Y'),  # DD/MM/YYYY format for exports
                'due_date': due_date.strftime('%d/%m/%Y'),     # DD/MM/YYYY format for exports
                'overdue_days': overdue_days,
                'closed': closed_date.strftime('%d/%m/%Y') if closed_date else '-',
                'resolution_time': resolution_time,
            })
        
        return export_data, dynamic_title, queryset.count()


@login_required
def export_enquiries_csv(request):
    """Export filtered enquiries to CSV format."""
    processor = ExportDataProcessor(request.GET, request.user)
    export_data, dynamic_title, total_count = processor.get_export_data()
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"{dynamic_title}_Export_{datetime.now().strftime('%Y-%m-%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Write CSV data
    writer = csv.DictWriter(response, fieldnames=[
        'reference', 'title', 'member', 'section', 'job_type', 'contact',
        'status', 'admin', 'created', 'updated', 'due_date', 'overdue_days', 'closed', 'resolution_time'
    ])
    
    writer.writeheader()
    writer.writerows(export_data)
    
    return response


@login_required
def export_enquiries_excel(request):
    """Export filtered enquiries to Excel format."""
    if not OPENPYXL_AVAILABLE:
        return JsonResponse({'error': 'Excel export not available - openpyxl not installed'}, status=500)
    
    processor = ExportDataProcessor(request.GET, request.user)
    export_data, dynamic_title, total_count = processor.get_export_data()
    
    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Enquiries Export"
    
    # Define headers
    headers = [
        'Reference', 'Title', 'Member', 'Section', 'Job Type', 'Contact',
        'Status', 'Admin', 'Created', 'Updated', 'Due Date', 'Overdue Days', 'Closed', 'Resolution Time'
    ]
    
    # Header styling
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Write data
    field_mapping = [
        'reference', 'title', 'member', 'section', 'job_type', 'contact',
        'status', 'admin', 'created', 'updated', 'due_date', 'overdue_days', 'closed', 'resolution_time'
    ]
    
    for row, enquiry_data in enumerate(export_data, 2):
        for col, field in enumerate(field_mapping, 1):
            ws.cell(row=row, column=col, value=enquiry_data[field])
    
    # Auto-size columns
    for col in range(1, len(headers) + 1):
        column_letter = get_column_letter(col)
        ws.column_dimensions[column_letter].width = 15
    
    # Create response
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"{dynamic_title}_Export_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def get_export_info(request):
    """Get information about the current export (count, title) via AJAX."""
    processor = ExportDataProcessor(request.GET, request.user)
    _, dynamic_title, total_count = processor.get_export_data()
    
    return JsonResponse({
        'title': dynamic_title,
        'count': total_count,
        'csv_url': f"/api/export/csv/?{urlencode(request.GET)}",
        'excel_url': f"/api/export/excel/?{urlencode(request.GET)}",
    })