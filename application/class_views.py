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

from datetime import date, datetime, time as dt_time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from .message_service import MessageService
from django.contrib.auth.mixins import LoginRequiredMixin
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

# URL name constants (avoids duplicated string literals - SonarQube S1192)
URL_ENQUIRY_LIST = "application:enquiry_list"
URL_ENQUIRY_DETAIL = "application:enquiry_detail"


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
        status = (
            filter_form.cleaned_data.get("status")
            if filter_form.is_valid()
            else filter_form.data.get("status")
        )
        if status and status != "all":
            hints.append("setting the status to 'All Enquiries'")

        # Check date range filter
        date_range = (
            filter_form.cleaned_data.get("date_range")
            if filter_form.is_valid()
            else filter_form.data.get("date_range")
        )
        if date_range and date_range != "all":
            hints.append("using the 'All time' date range")

        if hints:
            hint_text = " and ".join(hints)
            return f"No results found. Try {hint_text} to see more enquiries."
        else:
            return "No results found."

    def clean_filter_params(self, request):
        """Clean up URL parameters with smart custom date handling."""
        return DateRangeService.clean_url_parameters(request.GET)

    # Field name to ORM lookup mapping for simple filters
    _FIELD_LOOKUPS = {
        "member": "member",
        "admin": "admin",
        "section": "section",
        "job_type": "job_type",
        "service_type": "service_type",
        "contact": "contact",
        "ward": "member__ward",
    }

    def _apply_status_filter(self, queryset, cleaned_data):
        """Apply status filter to queryset."""
        status = cleaned_data.get("status")
        if not status:
            return queryset
        if status == "open":
            return queryset.filter(status__in=["new", "open"])
        return queryset.filter(status=status)

    def _apply_field_filters(self, queryset, cleaned_data):
        """Apply simple field filters from form cleaned data."""
        for field_name, lookup in self._FIELD_LOOKUPS.items():
            value = cleaned_data.get(field_name)
            if value:
                queryset = queryset.filter(**{lookup: value})
        return queryset

    def _apply_overdue_filter(self, queryset, cleaned_data):
        """Apply overdue-only filter if selected."""
        if not cleaned_data.get("overdue_only"):
            return queryset
        overdue_date = timezone.now() - timedelta(days=5)
        return queryset.filter(status__in=["new", "open"], created_at__lt=overdue_date)

    def _apply_search_filter(self, queryset, cleaned_data):
        """Apply search filter with performance limiting."""
        search_term = cleaned_data.get("search")
        if not search_term:
            return queryset

        queryset = EnquirySearchService.apply_search(queryset, search_term)

        # For performance: limit search results when searching all records
        has_narrowing_filter = any(
            [
                cleaned_data.get("status") != "all",
                cleaned_data.get("date_range") != "all",
                cleaned_data.get("member"),
                cleaned_data.get("admin"),
                cleaned_data.get("section"),
            ]
        )
        if not has_narrowing_filter:
            queryset = queryset[:500]

        return queryset

    def apply_filters(self, queryset, filter_form):
        """Apply filters to the queryset based on the form data."""
        if not filter_form.is_valid():
            return queryset

        queryset = DateRangeService.apply_date_filters_with_timezone(
            queryset, filter_form
        )
        cleaned_data = filter_form.cleaned_data
        queryset = self._apply_status_filter(queryset, cleaned_data)
        queryset = self._apply_field_filters(queryset, cleaned_data)
        queryset = self._apply_overdue_filter(queryset, cleaned_data)
        queryset = self._apply_search_filter(queryset, cleaned_data)

        return queryset


class EnquiryListView(LoginRequiredMixin, EnquiryFilterMixin, View):
    """
    Class-based view for enquiry list with advanced filtering.

    This replaces the large enquiry_list function-based view with
    better organized, reusable code.
    """

    def get(self, request):
        """Handle GET requests for enquiry list."""
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
        if not form_data.get("date_range"):
            if form_data.get("date_from") or form_data.get("date_to"):
                form_data["date_range"] = "custom"
            else:
                form_data["date_range"] = "12months"

        filter_form = EnquiryFilterForm(form_data)

        # Generate dynamic title based on active filters (used by template)
        from .services import EnquiryFilterService

        dynamic_title = EnquiryFilterService.generate_dynamic_title(filter_form)

        # Get centralized JavaScript date constants for consistency
        from .date_utils import get_javascript_date_constants

        # Always use server-side DataTables for optimal performance
        return render(
            request,
            "enquiry_list_serverside.html",
            {
                "filter_form": filter_form,
                "dynamic_title": dynamic_title,
                "today": timezone.now().date(),
                "js_date_constants": get_javascript_date_constants(),
            },
        )


class EnquiryDetailView(LoginRequiredMixin, DetailView):
    """
    Class-based view for enquiry details with history handling.
    """

    model = Enquiry
    template_name = "enquiry_detail.html"
    context_object_name = "enquiry"

    def get(self, request, *args, **kwargs):
        """Override to handle missing enquiries gracefully."""
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            # Get the enquiry ID from URL for the error message
            enquiry_id = kwargs.get("pk")
            messages.error(request, f"Enquiry with ID {enquiry_id} does not exist.")
            return redirect(URL_ENQUIRY_LIST)

    def get_queryset(self):
        """Optimize queryset with select_related."""
        return Enquiry.objects.select_related(
            "member", "admin__user", "section", "contact", "job_type"
        )

    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        enquiry = self.object

        # Get history and attachments
        context["history"] = enquiry.history.select_related("created_by").order_by(
            "-created_at"
        )
        context["attachments"] = enquiry.attachments.select_related(
            "uploaded_by"
        ).order_by("-uploaded_at")
        context["history_form"] = EnquiryHistoryForm()
        context["today"] = timezone.now().date()

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
            MessageService.success(request, "Note added successfully.")
            return redirect(URL_ENQUIRY_DETAIL, pk=self.object.pk)

        # If form is not valid, re-render with errors
        context = self.get_context_data(**kwargs)
        context["history_form"] = history_form
        return render(request, self.template_name, context)


class EnquiryCloseView(LoginRequiredMixin, View):
    """
    Class-based view for closing enquiries.
    """

    def _get_enquiry_or_error(self, request, pk):
        """Retrieve enquiry or return an error response."""
        try:
            return Enquiry.objects.get(pk=pk), None
        except Enquiry.DoesNotExist:
            messages.error(request, f"Enquiry with ID {pk} does not exist.")
            return None, redirect(URL_ENQUIRY_LIST)

    def _build_resolution_time_data(self, enquiry):
        """Build resolution time data dict for AJAX response."""
        from application.utils import calculate_business_days, calculate_calendar_days
        from application.templatetags.list_extras import resolution_time_color

        if not enquiry.closed_at:
            return {
                "business_days": None,
                "calendar_days": None,
                "display": "-",
                "color_class": "",
            }

        business_days = calculate_business_days(enquiry.created_at, enquiry.closed_at)
        calendar_days = calculate_calendar_days(enquiry.created_at, enquiry.closed_at)
        display = str(business_days) if business_days is not None else "-"
        color_class = (
            resolution_time_color(business_days) if business_days is not None else ""
        )

        return {
            "business_days": business_days,
            "calendar_days": calendar_days,
            "display": display,
            "color_class": color_class,
        }

    def _build_ajax_success_response(self, enquiry):
        """Build the JSON success response for a closed enquiry."""
        return JsonResponse(
            {
                "success": True,
                "message": f'Enquiry "{enquiry.reference}" has been closed.',
                "enquiry": {
                    "id": enquiry.id,
                    "status": enquiry.status,
                    "status_display": enquiry.get_status_display(),
                    "closed_at": (
                        enquiry.closed_at.isoformat() if enquiry.closed_at else None
                    ),
                    "closed_at_formatted": (
                        enquiry.closed_at.strftime("%Y-%m-%d")
                        if enquiry.closed_at
                        else "-"
                    ),
                    "service_type": enquiry.service_type,
                    "service_type_display": enquiry.get_service_type_display(),
                    "resolution_time": self._build_resolution_time_data(enquiry),
                },
            }
        )

    def _handle_ajax_close(self, request, enquiry, service_type):
        """Handle AJAX close request."""
        if not service_type:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Service type is required to close an enquiry.",
                }
            )
        try:
            closed = EnquiryService.close_enquiry(
                enquiry, request.user, service_type=service_type
            )
        except ValueError as e:
            return JsonResponse({"success": False, "message": str(e)})

        if not closed:
            return JsonResponse(
                {
                    "success": False,
                    "message": f'Enquiry "{enquiry.reference}" is already closed.',
                }
            )
        return self._build_ajax_success_response(enquiry)

    def _handle_standard_close(self, request, enquiry, pk, service_type):
        """Handle standard (non-AJAX) close request."""
        if not service_type:
            messages.error(request, "Service type is required to close an enquiry.")
            return redirect(URL_ENQUIRY_DETAIL, pk=pk)

        try:
            if EnquiryService.close_enquiry(
                enquiry, request.user, service_type=service_type
            ):
                messages.success(
                    request, f'Enquiry "{enquiry.reference}" has been closed.'
                )
            else:
                messages.warning(
                    request, f'Enquiry "{enquiry.reference}" is already closed.'
                )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect(URL_ENQUIRY_DETAIL, pk=pk)

        return self._resolve_redirect(request, pk, enquiry)

    def _resolve_redirect(self, request, pk, enquiry):
        """Determine where to redirect after closing."""
        referer = request.META.get("HTTP_REFERER", "")
        if referer:
            if f"/enquiries/{pk}/" in referer and "/edit" not in referer:
                return redirect(URL_ENQUIRY_DETAIL, pk=enquiry.pk)
            if "/enquiries/" in referer or "/home/" in referer:
                return HttpResponseRedirect(referer)
        return redirect(URL_ENQUIRY_LIST)

    def post(self, request, pk):
        """Handle POST requests to close an enquiry."""
        enquiry, error_response = self._get_enquiry_or_error(request, pk)
        if error_response:
            return error_response

        service_type = request.POST.get("service_type", "").strip()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return self._handle_ajax_close(request, enquiry, service_type)

        return self._handle_standard_close(request, enquiry, pk, service_type)
