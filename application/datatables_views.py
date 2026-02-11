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
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .class_views import EnquiryFilterMixin
from .forms import EnquiryFilterForm
from .models import Enquiry
from .search_service import EnquirySearchService

# Template tags not needed for server-side processing

# Status badge mapping: status -> (css_class, display_text_override)
# None for display_text_override means use enquiry.get_status_display()
_STATUS_BADGE_MAP = {
    "new": ("bg-primary", "Open"),
    "open": ("bg-primary", None),
    "closed": ("bg-success", None),
}
_STATUS_BADGE_DEFAULT = ("bg-secondary", None)

# Threshold-based color mappings: list of (upper_bound, css_class) pairs,
# checked in order; the final fallback is the last element with no bound.
_RESOLUTION_THRESHOLDS = [(5, "text-success"), (10, "text-warning")]
_RESOLUTION_FALLBACK = "text-danger"

_OVERDUE_THRESHOLDS = [(2, "text-warning fw-bold"), (5, "text-danger fw-bold")]
_OVERDUE_FALLBACK = "fw-bold text-white bg-danger px-2 py-1 rounded"


def _color_for_value(value, thresholds, fallback):
    """Return the CSS class for a value based on threshold breakpoints."""
    for limit, css_class in thresholds:
        if value <= limit:
            return css_class
    return fallback


def _to_date_str(value):
    """Convert a datetime or date to a YYYY-MM-DD string."""
    if hasattr(value, "date"):
        value = value.date()
    return value.strftime("%Y-%m-%d")


def _build_filter_url(base_url, current_filters, **kwargs):
    """Build a URL that preserves current filters and adds/overrides with kwargs."""
    merged = {}
    if current_filters:
        merged.update(current_filters)
    merged.update(kwargs)
    return f"{base_url}?{urlencode(merged)}"


def _filter_link(base_url, current_filters, filter_kwargs, display_text, title):
    """Build an anchor tag that applies a filter while preserving existing ones."""
    url = _build_filter_url(base_url, current_filters, **filter_kwargs)
    return (
        f'<a href="{url}" class="text-decoration-none" '
        f'title="{title}">{escape(display_text)}</a>'
    )


def _optional_filter_link(
    base_url,
    current_filters,
    obj,
    filter_key,
    display_attr,
    title,
    fallback="Not assigned",
):
    """Build a filter link for an optional FK field, or return fallback text."""
    if not obj:
        return fallback
    display_text = getattr(obj, display_attr)
    return _filter_link(
        base_url, current_filters, {filter_key: obj.id}, display_text, title
    )


class DataTablesServerSide:
    """Handle DataTables server-side processing for enquiries."""

    def __init__(self, request, request_data=None):
        self.request = request
        if request_data is None:
            request_data = request.GET

        self.draw = int(request_data.get("draw", 1))
        self.start = max(0, int(request_data.get("start", 0)))  # Ensure non-negative
        self.length = int(request_data.get("length", 10))

        # Handle "All" option (-1) by setting a reasonable maximum
        if self.length == -1:
            self.length = 10000  # Large but manageable number

        # DataTables search
        self.search_value = request_data.get("search[value]", "").strip()

        # DataTables ordering
        self.order_column = int(
            request_data.get("order[0][column]", 9)
        )  # Default to Created column
        self.order_dir = request_data.get("order[0][dir]", "desc")

        # Column mapping for ordering
        self.columns = [
            "reference",  # 0
            "title",  # 1
            "member__first_name",  # 2
            "section__name",  # 3
            "job_type__name",  # 4
            "service_type",  # 5 - Service Type
            "contact__name",  # 6
            "status",  # 7
            "admin__user__first_name",  # 8
            "created_at",  # 9
            "updated_at",  # 10
            "due_date",  # 11 - Due Date (sortable database field)
            None,  # 12 - Overdue Days (calculated, not sortable)
            "closed_at",  # 13
            None,  # 14 - Resolution Time (calculated)
            None,  # 15 - Actions (not sortable)
        ]

    def get_base_queryset(self, filter_mixin, filter_form):
        """Get the base queryset with filters applied."""
        # Check if we have search terms (either from DataTables or form)
        form_search = ""
        if hasattr(filter_form, "cleaned_data") and filter_form.cleaned_data:
            form_search = filter_form.cleaned_data.get("search", "")

        # Start with optimized queryset
        if not self.search_value and not form_search:
            queryset = Enquiry.objects.select_related(
                "member", "admin__user", "section", "job_type", "contact"
            ).defer("description")
        else:
            queryset = Enquiry.objects.select_related(
                "member", "admin__user", "section", "job_type", "contact"
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
            if self.order_dir == "desc":
                order_field = f"-{order_field}"
            queryset = queryset.order_by(order_field)
        else:
            # Default ordering
            queryset = queryset.order_by("-created_at")

        return queryset

    @staticmethod
    def _get_status_badge(enquiry):
        """Return (status_class, status_text) for the enquiry status badge."""
        status_class, status_text = _STATUS_BADGE_MAP.get(
            enquiry.status, _STATUS_BADGE_DEFAULT
        )
        if status_text is None:
            status_text = enquiry.get_status_display()
        return status_class, status_text

    @staticmethod
    def _get_resolution_time_html(enquiry):
        """Return HTML for resolution time display."""
        if enquiry.status != "closed" or not enquiry.closed_at:
            return "-"

        from application.utils import calculate_business_days

        business_days = calculate_business_days(enquiry.created_at, enquiry.closed_at)
        if business_days is None:
            return "-"

        color_class = _color_for_value(
            business_days, _RESOLUTION_THRESHOLDS, _RESOLUTION_FALLBACK
        )
        return f'<span class="{color_class}">{business_days}</span>'

    @staticmethod
    def _get_actions_html(enquiry):
        """Return HTML for the action buttons column."""
        detail_url = reverse("application:enquiry_detail", args=[enquiry.id])
        ref_escaped = escape(enquiry.reference or "No Ref")
        title_escaped = escape(enquiry.title)

        view_btn = (
            f'<a href="{detail_url}" class="btn btn-outline-primary"'
            f' title="View enquiry details">'
            f'<i class="bi bi-eye"></i> View</a>'
        )

        if enquiry.status != "closed":
            edit_url = reverse("application:enquiry_edit", args=[enquiry.id])
            extra_btns = (
                f'<a href="{edit_url}" class="btn btn-outline-secondary"'
                f' title="Edit this enquiry">'
                f'<i class="bi bi-pencil"></i> Edit</a>'
                f'<button type="button" class="btn btn-outline-danger" '
                f'data-bs-toggle="modal" '
                f'data-bs-target="#enquiryActionModal" '
                f'data-enquiry-id="{enquiry.id}" '
                f'data-enquiry-ref="{ref_escaped}" '
                f'data-enquiry-title="{title_escaped}" '
                f'data-action="close" '
                f'title="Close this enquiry">'
                f'<i class="bi bi-x-circle"></i> Close</button>'
            )
        else:
            extra_btns = (
                f'<button type="button" class="btn btn-outline-success" '
                f'data-bs-toggle="modal" '
                f'data-bs-target="#enquiryActionModal" '
                f'data-enquiry-id="{enquiry.id}" '
                f'data-enquiry-ref="{ref_escaped}" '
                f'data-enquiry-title="{title_escaped}" '
                f'data-action="reopen" '
                f'title="Re-open this enquiry">'
                f'<i class="bi bi-arrow-clockwise"></i> Re-open</button>'
            )

        return (
            f'<div class="btn-group btn-group-sm" role="group">'
            f"{view_btn}{extra_btns}</div>"
        )

    @staticmethod
    def _get_overdue_info(enquiry, today):
        """Return (due_date, is_overdue, overdue_days_html)."""
        due_date = (
            enquiry.due_date.date()
            if hasattr(enquiry.due_date, "date")
            else enquiry.due_date
        )
        is_overdue = due_date < today and enquiry.status != "closed"

        if not is_overdue:
            return due_date, False, "-"

        from application.utils import calculate_business_days

        overdue_business_days = calculate_business_days(due_date, today)
        if not overdue_business_days or overdue_business_days <= 0:
            return due_date, True, "-"

        color_class = _color_for_value(
            overdue_business_days, _OVERDUE_THRESHOLDS, _OVERDUE_FALLBACK
        )
        overdue_days_html = (
            f'<span class="{color_class}" '
            f'title="{overdue_business_days} business days overdue">'
            f"{overdue_business_days}</span>"
        )
        return due_date, True, overdue_days_html

    def format_enquiry_row(self, enquiry, today, current_filters=None):
        """Format a single enquiry row for DataTables."""
        base_url = reverse("application:enquiry_list")
        detail_url = reverse("application:enquiry_detail", args=[enquiry.id])

        status_class, status_text = self._get_status_badge(enquiry)
        resolution_time_html = self._get_resolution_time_html(enquiry)
        actions_html = self._get_actions_html(enquiry)
        due_date, is_overdue, overdue_days_html = self._get_overdue_info(enquiry, today)

        due_date_class = "text-danger fw-bold" if is_overdue else ""

        # Admin display
        admin_html = "Unassigned"
        if enquiry.admin and enquiry.admin.user:
            admin_name = (
                enquiry.admin.user.get_full_name() or enquiry.admin.user.username
            )
            admin_html = _filter_link(
                base_url,
                current_filters,
                {"admin": enquiry.admin.id},
                admin_name,
                "Filter by this admin",
            )

        # Closed date display
        closed_html = "-"
        if enquiry.status == "closed" and enquiry.closed_at:
            closed_html = _to_date_str(enquiry.closed_at)

        # Service type display
        service_type_html = "Not set"
        if enquiry.service_type:
            service_type_html = _filter_link(
                base_url,
                current_filters,
                {"service_type": enquiry.service_type},
                enquiry.get_service_type_display(),
                "Filter by this service type",
            )

        # Build row data
        row_data = [
            f'<a href="{detail_url}" class="text-decoration-none fw-bold">{escape(enquiry.reference or "No Ref")}</a>',  # 0
            escape(
                enquiry.title[:50] + ("..." if len(enquiry.title) > 50 else "")
            ),  # 1
            _filter_link(
                base_url,
                current_filters,
                {"member": enquiry.member.id},
                enquiry.member.full_name,
                "Filter by this member",
            ),  # 2
            _optional_filter_link(
                base_url,
                current_filters,
                enquiry.section,
                "section",
                "name",
                "Filter by this section",
            ),  # 3
            _optional_filter_link(
                base_url,
                current_filters,
                enquiry.job_type,
                "job_type",
                "name",
                "Filter by this job type",
            ),  # 4
            service_type_html,  # 5 - Service Type
            _optional_filter_link(
                base_url,
                current_filters,
                enquiry.contact,
                "contact",
                "name",
                "Filter by this contact",
            ),  # 6
            f'<span class="badge {status_class}">{escape(status_text)}</span>',  # 7
            admin_html,  # 8
            _to_date_str(enquiry.created_at),  # 9
            _to_date_str(enquiry.updated_at),  # 10
            f'<span class="{due_date_class}">{due_date.strftime("%Y-%m-%d")}</span>',  # 11
            overdue_days_html,  # 12
            closed_html,  # 13
            resolution_time_html,  # 14
            actions_html,  # 15
        ]

        # Add row attributes for styling (DataTables will use DT_RowClass)
        row_attrs = {
            "DT_RowId": f"enquiry-{enquiry.id}",
            "DT_RowData": {"enquiry-id": enquiry.id},
        }

        if is_overdue:
            row_attrs["DT_RowClass"] = "table-warning"

        return {"data": row_data, **row_attrs}

    @staticmethod
    def _extract_current_filters(filter_form):
        """Extract current filter values from a validated form for URL building."""
        if not hasattr(filter_form, "cleaned_data") or not filter_form.cleaned_data:
            return {}

        current_filters = {}
        for field_name, value in filter_form.cleaned_data.items():
            if not value or value == "" or value == "all":
                continue
            # Convert model instances to their IDs for URL parameters
            if hasattr(value, "id"):
                current_filters[field_name] = str(value.id)
            elif isinstance(value, bool):
                # Only include True boolean values (like overdue_only)
                if value:
                    current_filters[field_name] = "on"
            else:
                current_filters[field_name] = str(value)
        return current_filters

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
        paginated_queryset = queryset[self.start : self.start + self.length]

        # Extract current filters from filter_form for contextual linking
        current_filters = self._extract_current_filters(filter_form)

        # Format data for DataTables
        today = timezone.now().date()
        data = []
        for enquiry in paginated_queryset:
            row_data = self.format_enquiry_row(enquiry, today, current_filters)
            data.append(row_data["data"])  # DataTables expects just the data array

        # Generate dynamic title based on current filters
        from .services import EnquiryFilterService

        dynamic_title = EnquiryFilterService.generate_dynamic_title(filter_form)

        return {
            "draw": self.draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
            "dynamicTitle": dynamic_title,  # Add dynamic title to response
        }


@login_required
@csrf_protect
@require_http_methods(["POST"])
def enquiry_list_datatables(request):
    """
    AJAX endpoint for DataTables server-side processing.

    This handles pagination, searching, and sorting on the server side,
    dramatically improving performance for large datasets.
    """
    try:
        request_data = request.POST

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

        return JsonResponse(
            {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "draw": request_data.get("draw", 1),
                "recordsTotal": 0,
                "recordsFiltered": 0,
                "data": [],
            },
            status=500,
        )
