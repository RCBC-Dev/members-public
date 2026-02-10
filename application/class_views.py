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
Class-based views for the Members Enquiries System.

This module provides class-based views for complex functionality,
offering better code organization and reusability.
"""

import time
from datetime import date, datetime, time as dt_time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from .message_service import MessageService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView

from .forms import EnquiryFilterForm, EnquiryHistoryForm
from .models import Enquiry, EnquiryHistory
from .services import EnquiryService
from .utils import strip_html_tags
from .date_range_service import DateRangeService
from .search_service import EnquirySearchService


class EnquiryFilterMixin:
    """Mixin to handle enquiry filtering logic."""
    
    def _dates_match_predefined_range(self, date_from_str, date_to_str):
        """Check if the provided dates match any predefined range using centralized date system."""
        return DateRangeService.dates_match_predefined_range(date_from_str, date_to_str)
    
    def get_default_filter_params(self):
        """Get default filter parameters for first visit."""
        return DateRangeService.get_default_filter_params()
    
    def get_no_results_hint(self, filter_form, result_count):
        """Generate smart hint message when no results are found."""
        if result_count > 0:
            return None
            
        # Check what restrictive filters are applied
        hints = []
        
        # Check status filter
        status = filter_form.cleaned_data.get('status') if filter_form.is_valid() else filter_form.data.get('status')
        if status and status != 'all':
            hints.append("setting the status to 'All Enquiries'")
        
        # Check date range filter  
        date_range = filter_form.cleaned_data.get('date_range') if filter_form.is_valid() else filter_form.data.get('date_range')
        if date_range and date_range != 'all':
            hints.append("using the 'All time' date range")
        
        if hints:
            hint_text = " and ".join(hints)
            return f"No results found. Try {hint_text} to see more enquiries."
        else:
            return "No results found."
    
    def clean_filter_params(self, request):
        """Clean up URL parameters with smart custom date handling."""
        return DateRangeService.clean_url_parameters(request.GET)
    
    def apply_filters(self, queryset, filter_form):
        """Apply filters to the queryset based on the form data."""
        if not filter_form.is_valid():
            return queryset
        
        # Handle date filtering using centralized service
        queryset = DateRangeService.apply_date_filters_with_timezone(queryset, filter_form)

        # Apply all other filters
        status = filter_form.cleaned_data.get('status')
        if status:
            if status == 'open':
                # 'Open' filter includes both 'new' and 'open' statuses
                queryset = queryset.filter(status__in=['new', 'open'])
            else:
                queryset = queryset.filter(status=status)

        if filter_form.cleaned_data.get('member'):
            queryset = queryset.filter(member=filter_form.cleaned_data['member'])

        if filter_form.cleaned_data.get('admin'):
            queryset = queryset.filter(admin=filter_form.cleaned_data['admin'])

        if filter_form.cleaned_data.get('section'):
            queryset = queryset.filter(section=filter_form.cleaned_data['section'])

        if filter_form.cleaned_data.get('job_type'):
            queryset = queryset.filter(job_type=filter_form.cleaned_data['job_type'])

        if filter_form.cleaned_data.get('service_type'):
            queryset = queryset.filter(service_type=filter_form.cleaned_data['service_type'])

        if filter_form.cleaned_data.get('contact'):
            queryset = queryset.filter(contact=filter_form.cleaned_data['contact'])

        if filter_form.cleaned_data.get('ward'):
            queryset = queryset.filter(member__ward=filter_form.cleaned_data['ward'])

        if filter_form.cleaned_data.get('overdue_only'):
            overdue_date = timezone.now() - timedelta(days=5)
            queryset = queryset.filter(
                status__in=['new', 'open'],
                created_at__lt=overdue_date
            )

        # Apply search filter (searches reference, title, description)
        # Note: History note search temporarily disabled for performance - causes expensive JOINs
        if filter_form.cleaned_data.get('search'):
            search_term = filter_form.cleaned_data['search']
            queryset = EnquirySearchService.apply_search(queryset, search_term)
        
        # For performance: limit search results when searching all records
        if filter_form.cleaned_data.get('search') and not any([
            filter_form.cleaned_data.get('status') != 'all',
            filter_form.cleaned_data.get('date_range') != 'all',
            filter_form.cleaned_data.get('member'),
            filter_form.cleaned_data.get('admin'),
            filter_form.cleaned_data.get('section'),
        ]):
            # Searching everything - limit to reasonable number for performance
            queryset = queryset[:500]  # Limit to 500 most recent results
        
        return queryset


class EnquiryListView(LoginRequiredMixin, EnquiryFilterMixin, View):
    """
    Class-based view for enquiry list with advanced filtering.
    
    This replaces the large enquiry_list function-based view with
    better organized, reusable code.
    """
    
    def get(self, request):
        """Handle GET requests for enquiry list."""
        start_time = time.time()
        initial_queries = len(connection.queries)

        # Server-side processing handles all queryset operations, 
        # so we don't need to build the full queryset here anymore

        # Handle first visit - redirect with default parameters
        if not request.GET:
            default_params = self.get_default_filter_params()
            return HttpResponseRedirect(f"{request.path}?{urlencode(default_params)}")

        # Clean up URL parameters
        clean_params, has_empty_params = self.clean_filter_params(request)

        # Redirect with clean URL if needed
        if has_empty_params:
            if clean_params:
                return HttpResponseRedirect(f"{request.path}?{urlencode(clean_params)}")
            else:
                return HttpResponseRedirect(request.path)

        # Initialize filter form for display with standardized parameters
        form_data = request.GET.copy()

        # Ensure we always have a date_range parameter
        if not form_data.get('date_range'):
            if form_data.get('date_from') or form_data.get('date_to'):
                form_data['date_range'] = 'custom'
            else:
                form_data['date_range'] = '12months'

        filter_form = EnquiryFilterForm(form_data)

        # Generate dynamic title based on active filters (used by template)
        from .services import EnquiryFilterService
        dynamic_title = EnquiryFilterService.generate_dynamic_title(filter_form)

        # Get centralized JavaScript date constants for consistency
        from .date_utils import get_javascript_date_constants

        # Always use server-side DataTables for optimal performance
        return render(request, 'enquiry_list_serverside.html', {
            'filter_form': filter_form,
            'dynamic_title': dynamic_title,
            'today': timezone.now().date(),
            'js_date_constants': get_javascript_date_constants(),
        })


class EnquiryDetailView(LoginRequiredMixin, DetailView):
    """
    Class-based view for enquiry details with history handling.
    """
    model = Enquiry
    template_name = 'enquiry_detail.html'
    context_object_name = 'enquiry'
    
    def get(self, request, *args, **kwargs):
        """Override to handle missing enquiries gracefully."""
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            # Get the enquiry ID from URL for the error message
            enquiry_id = kwargs.get('pk')
            messages.error(request, f'Enquiry with ID {enquiry_id} does not exist.')
            return redirect('application:enquiry_list')
    
    def get_queryset(self):
        """Optimize queryset with select_related."""
        return Enquiry.objects.select_related(
            'member', 'admin__user', 'section', 'contact', 'job_type'
        )
    
    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        enquiry = self.object
        
        # Get history and attachments
        context['history'] = enquiry.history.select_related('created_by').order_by('-created_at')
        context['attachments'] = enquiry.attachments.select_related('uploaded_by').order_by('-uploaded_at')
        context['history_form'] = EnquiryHistoryForm()
        context['today'] = timezone.now().date()
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests for adding history notes."""
        self.object = self.get_object()
        history_form = EnquiryHistoryForm(request.POST)

        if history_form.is_valid():
            history_entry = history_form.save(commit=False)
            history_entry.enquiry = self.object
            history_entry.created_by = request.user

            # Note type is now controlled by the user via the dropdown
            # No automatic override needed - user has full control

            history_entry.save()
            MessageService.success(request, 'Note added successfully.')
            return redirect('application:enquiry_detail', pk=self.object.pk)

        # If form is not valid, re-render with errors
        context = self.get_context_data(**kwargs)
        context['history_form'] = history_form
        return render(request, self.template_name, context)


class EnquiryCloseView(LoginRequiredMixin, View):
    """
    Class-based view for closing enquiries.
    """
    
    def post(self, request, pk):
        """Handle POST requests to close an enquiry."""
        try:
            enquiry = Enquiry.objects.get(pk=pk)
        except Enquiry.DoesNotExist:
            messages.error(request, f'Enquiry with ID {pk} does not exist.')
            return redirect('application:enquiry_list')

        # Extract service_type from POST data
        service_type = request.POST.get('service_type', '').strip()

        # Handle AJAX requests differently
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                if not service_type:
                    return JsonResponse({
                        'success': False,
                        'message': 'Service type is required to close an enquiry.'
                    })

                if EnquiryService.close_enquiry(enquiry, request.user, service_type=service_type):
                    # Calculate resolution time data for AJAX response
                    from application.utils import calculate_business_days, calculate_calendar_days
                    from application.templatetags.list_extras import resolution_time_color

                    business_days = None
                    calendar_days = None
                    resolution_time_display = '-'
                    resolution_time_color_class = ''

                    if enquiry.closed_at:
                        business_days = calculate_business_days(enquiry.created_at, enquiry.closed_at)
                        calendar_days = calculate_calendar_days(enquiry.created_at, enquiry.closed_at)

                        if business_days is not None:
                            resolution_time_display = str(business_days)
                            resolution_time_color_class = resolution_time_color(business_days)

                    return JsonResponse({
                        'success': True,
                        'message': f'Enquiry "{enquiry.reference}" has been closed.',
                        'enquiry': {
                            'id': enquiry.id,
                            'status': enquiry.status,
                            'status_display': enquiry.get_status_display(),
                            'closed_at': enquiry.closed_at.isoformat() if enquiry.closed_at else None,
                            'closed_at_formatted': enquiry.closed_at.strftime('%Y-%m-%d') if enquiry.closed_at else '-',
                            'service_type': enquiry.service_type,
                            'service_type_display': enquiry.get_service_type_display(),
                            'resolution_time': {
                                'business_days': business_days,
                                'calendar_days': calendar_days,
                                'display': resolution_time_display,
                                'color_class': resolution_time_color_class
                            }
                        }
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': f'Enquiry "{enquiry.reference}" is already closed.'
                    })
            except ValueError as e:
                return JsonResponse({'success': False, 'message': str(e)})

        # Non-AJAX requests (existing behavior)
        if not service_type:
            messages.error(request, 'Service type is required to close an enquiry.')
            return redirect('application:enquiry_detail', pk=pk)

        try:
            if EnquiryService.close_enquiry(enquiry, request.user, service_type=service_type):
                messages.success(request, f'Enquiry "{enquiry.reference}" has been closed.')
            else:
                messages.warning(request, f'Enquiry "{enquiry.reference}" is already closed.')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('application:enquiry_detail', pk=pk)

        # Redirect back to source page (list/dashboard) or detail if coming from detail page
        referer = request.META.get('HTTP_REFERER', '')
        if referer:
            # If coming from enquiry detail page, go back to detail
            if f'/enquiries/{pk}/' in referer and '/edit' not in referer:
                return redirect('application:enquiry_detail', pk=enquiry.pk)
            # If coming from enquiry list or dashboard, preserve the URL with filters
            elif '/enquiries/' in referer or '/home/' in referer:
                return HttpResponseRedirect(referer)

        # Default fallback to enquiry list
        return redirect('application:enquiry_list')