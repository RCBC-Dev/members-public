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

# Standard library imports
import json
import logging
import os
import tempfile
import uuid
from datetime import date, datetime, timedelta
from email.utils import parseaddr
from urllib.parse import urlencode

# Third-party imports
from dateutil.relativedelta import relativedelta

# Django imports
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

# Local imports
from .file_security import FileUploadService
from .forms import EnquiryFilterForm, EnquiryHistoryForm, StaffEnquiryForm
from .models import (
    Admin,
    Contact,
    Enquiry,
    EnquiryAttachment,
    EnquiryHistory,
    JobType,
    Member,
    Section,
    Ward,
)
from .services import (
    EmailProcessingService,
    EnquiryFilterService,
    EnquiryService,
    MemberService,
)
from .email_service import EmailProcessingService as UnifiedEmailService
from .utils import (
    _resize_image_if_needed,
    admin_required,
    calculate_month_range_from_keys,
    create_json_response,
    DateRangeUtility,
    generate_last_months,
    parse_msg_file,
    safe_file_path_join,
    strip_html_tags,
    validate_file_security,
)
from .message_service import MessageService

# Initialize logger and user model
logger = logging.getLogger(__name__)
User = get_user_model()

# ---------------------------------------------------------------------------
# Shared string constants (SonarQube S1192 - avoid duplicated string literals)
# ---------------------------------------------------------------------------
URL_ENQUIRY_LIST = "application:enquiry_list"
URL_ENQUIRY_DETAIL = "application:enquiry_detail"
MSG_NO_FILE_PROVIDED = "No file provided"


# ---------------------------------------------------------------------------
# Helper functions to reduce cognitive complexity of view functions
# ---------------------------------------------------------------------------


def _get_enquiry_or_redirect(pk, request, redirect_target=URL_ENQUIRY_LIST):
    """Fetch an enquiry by pk or return a redirect response if not found."""
    try:
        return Enquiry.objects.get(pk=pk), None
    except Enquiry.DoesNotExist:
        messages.error(request, f"Enquiry with ID {pk} does not exist.")
        return None, redirect(redirect_target)


def _handle_attach_only_request(enquiry, user, extracted_images_json):
    """Handle attach-only POST requests during enquiry edit."""
    try:
        EnquiryService.add_attachments_to_enquiry(
            enquiry=enquiry,
            user=user,
            extracted_images_json=extracted_images_json,
        )
        return create_json_response(True, message="Images attached successfully")
    except Exception as e:
        logger.error(f"Error attaching images to enquiry {enquiry.pk}: {e}")
        return JsonResponse({"success": False, "error": str(e)})


def _get_edit_success_message(enquiry, changes, has_new_attachments):
    """Return the appropriate success message for an enquiry edit."""
    if not changes and not has_new_attachments:
        return "info", f'No changes made to enquiry "{enquiry.reference}".'
    if changes and has_new_attachments:
        return (
            "success",
            f'Enquiry "{enquiry.reference}" updated successfully with new attachments.',
        )
    if changes:
        return "success", f'Enquiry "{enquiry.reference}" updated successfully.'
    return "success", f'New attachments added to enquiry "{enquiry.reference}".'


def _handle_enquiry_edit_post(request, enquiry, form, extracted_images_json):
    """Process a regular (non-attach-only) form submission for enquiry edit."""
    if not form.is_valid():
        return None  # Signal that form is invalid; caller will re-render

    original_enquiry = Enquiry.objects.get(pk=enquiry.pk)
    changes = EnquiryService.track_enquiry_changes(original_enquiry, form.cleaned_data)
    enquiry = form.save()

    if changes:
        EnquiryService.create_field_change_history_entries(
            enquiry, changes, request.user
        )

    has_new_attachments = False
    if extracted_images_json:
        EnquiryService.add_attachments_to_enquiry(
            enquiry=enquiry,
            user=request.user,
            extracted_images_json=extracted_images_json,
        )
        has_new_attachments = True

    msg_type, msg_text = _get_edit_success_message(
        enquiry, changes, has_new_attachments
    )
    getattr(MessageService, msg_type)(request, msg_text)
    return redirect(URL_ENQUIRY_DETAIL, pk=enquiry.pk)


def _redirect_to_referer_or_detail(request, pk, allowed_paths=None):
    """Redirect to HTTP_REFERER if it matches allowed paths, else to enquiry detail."""
    referer = request.META.get("HTTP_REFERER", "")
    if allowed_paths is None:
        allowed_paths = ["/enquiries/", "/home/"]
    if referer and any(path in referer for path in allowed_paths):
        return HttpResponseRedirect(referer)
    return redirect(URL_ENQUIRY_DETAIL, pk=pk)


def _is_ajax(request):
    """Check if the request is an AJAX request."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _build_reopen_ajax_success(enquiry):
    """Build the JSON response data for a successful AJAX reopen."""
    return JsonResponse(
        {
            "success": True,
            "message": f'Enquiry "{enquiry.reference}" has been re-opened successfully.',
            "enquiry": {
                "id": enquiry.id,
                "status": enquiry.status,
                "status_display": enquiry.get_status_display(),
                "closed_at": None,
                "closed_at_formatted": "-",
                "resolution_time": {
                    "business_days": None,
                    "calendar_days": None,
                    "display": "-",
                    "color_class": "",
                },
            },
        }
    )


def _handle_reopen_missing_reason(request, pk):
    """Handle the case where reopen is called without a reason."""
    if _is_ajax(request):
        return JsonResponse(
            {
                "success": False,
                "message": "A reason is required to re-open the enquiry.",
            }
        )
    messages.error(request, "A reason is required to re-open the enquiry.")
    return _redirect_to_referer_or_detail(request, pk)


def _handle_reopen_redirect(request, pk, enquiry):
    """Handle post-reopen redirect for non-AJAX requests."""
    messages.success(
        request, f'Enquiry "{enquiry.reference}" has been re-opened successfully.'
    )
    referer = request.META.get("HTTP_REFERER", "")
    if referer:
        if f"/enquiries/{pk}/" in referer and "/edit" not in referer:
            return redirect(URL_ENQUIRY_DETAIL, pk=enquiry.pk)
        if "/enquiries/" in referer or "/home/" in referer:
            return HttpResponseRedirect(referer)
    return redirect(URL_ENQUIRY_LIST)


def _get_upload_file_type(uploaded_file):
    """Determine the type of an uploaded file. Returns (file_type, error_response) tuple."""
    file_ext = os.path.splitext(uploaded_file.name.lower())[1]

    image_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tiff",
        ".tif",
        ".mpo",
    }
    document_extensions = {".pdf", ".doc", ".docx"}

    if file_ext in image_extensions:
        return "image", None
    if file_ext in document_extensions:
        return "document", None

    error_msg = (
        f'File type not supported. Allowed: images ({", ".join(sorted(image_extensions))}) '
        f'and documents ({", ".join(sorted(document_extensions))})'
    )
    return None, JsonResponse({"success": False, "error": error_msg})


def _handle_file_upload(uploaded_file, file_type):
    """Upload a file using the appropriate service method."""
    if file_type == "image":
        return FileUploadService.handle_image_upload(uploaded_file, "")
    return FileUploadService.handle_document_upload(uploaded_file, "documents")


def _build_upload_response(result, file_type, is_image):
    """Build response data dict for a successful file upload."""
    response_data = {
        "filename": result["file_path"],
        "original_name": result["original_filename"],
        "size": result["file_size"],
        "url": result["file_url"],
        "file_type": file_type,
    }
    if is_image:
        response_data.update(
            {
                "original_size": result.get("original_size", result["file_size"]),
                "was_resized": result.get("was_resized", False),
            }
        )
    return response_data


def _create_attachment_for_enquiry(enquiry, result, request):
    """Create an attachment record and history entry for an existing enquiry."""
    attachment = EnquiryAttachment.objects.create(
        enquiry=enquiry,
        filename=result["original_filename"],
        file_path=result["file_path"],
        file_size=result["file_size"],
        uploaded_by=request.user,
    )
    history_note = f"1 file(s) manually attached: {result['original_filename']}"
    EnquiryHistory.objects.create(
        enquiry=enquiry,
        note=history_note,
        note_type="attachment_added",
        created_by=request.user,
    )
    logger.info(
        f"File attached to enquiry {enquiry.id}: "
        f"{request.FILES.get('photo_file', request.FILES.get('file')).name} -> {result['file_path']}"
    )
    return attachment


def _calculate_months_back_for_dashboard(date_range, date_range_info, current_date):
    """Calculate months_back and possibly adjusted current_date for performance dashboard."""
    if date_range == "all":
        earliest_enquiry = Enquiry.objects.order_by("created_at").first()
        if earliest_enquiry:
            start_date = earliest_enquiry.created_at.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            months_back = (
                (current_date.year - start_date.year) * 12
                + current_date.month
                - start_date.month
            )
        else:
            months_back = 12
        return months_back, current_date

    if date_range == "custom" and date_range_info.date_from and date_range_info.date_to:
        start_date = date_range_info.date_from
        end_date = date_range_info.date_to
        months_back = (
            (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
        ) + 1
        return months_back, end_date

    return date_range_info.months or 12, current_date


def _compute_sla_counts(closed_enquiries):
    """Compute within-SLA and outside-SLA counts for closed enquiries."""
    from .utils import calculate_business_days

    within_sla = 0
    outside_sla = 0
    for enquiry in closed_enquiries:
        if not (enquiry.created_at and enquiry.closed_at):
            continue
        business_days_to_close = calculate_business_days(
            enquiry.created_at, enquiry.closed_at
        )
        if business_days_to_close is not None and business_days_to_close <= 5:
            within_sla += 1
        else:
            outside_sla += 1
    return within_sla, outside_sla


def _collect_month_data(months_back, current_date, service_type):
    """Collect monthly created/closed/SLA data for the performance dashboard."""
    months_data = []
    for i in range(months_back - 1, -1, -1):
        month_date = current_date.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ) - relativedelta(months=i)
        next_month = month_date + relativedelta(months=1)

        created_query = Enquiry.objects.filter(
            created_at__gte=month_date, created_at__lt=next_month
        )
        if service_type:
            created_query = created_query.filter(service_type=service_type)

        closed_query = Enquiry.objects.filter(
            closed_at__gte=month_date, closed_at__lt=next_month, status="closed"
        )
        if service_type:
            closed_query = closed_query.filter(service_type=service_type)

        closed_within_sla, closed_outside_sla = _compute_sla_counts(closed_query)

        still_open_query = Enquiry.objects.filter(
            created_at__gte=month_date,
            created_at__lt=next_month,
            status__in=["new", "open"],
        )
        if service_type:
            still_open_query = still_open_query.filter(service_type=service_type)

        months_data.append(
            {
                "month": month_date.strftime("%b %Y"),
                "created": created_query.count(),
                "closed_within_sla": closed_within_sla,
                "closed_outside_sla": closed_outside_sla,
                "created_still_open": still_open_query.count(),
            }
        )
    return months_data


def _apply_date_and_member_filters(
    queryset, date_from, date_to, member_id, service_type
):
    """Apply common date range, member, and service type filters to a queryset."""
    if date_from:
        queryset = queryset.filter(created_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__lte=date_to)
    if member_id:
        queryset = queryset.filter(member_id=member_id)
    if service_type:
        queryset = queryset.filter(service_type=service_type)
    return queryset


def _calculate_business_days_stats(enquiries):
    """Calculate business day statistics for a queryset of closed enquiries."""
    from .utils import calculate_business_days

    enquiry_list = []
    total_business_days = 0
    valid_count = 0

    for enquiry in enquiries:
        if not (enquiry.created_at and enquiry.closed_at):
            continue
        business_days = calculate_business_days(enquiry.created_at, enquiry.closed_at)
        if business_days is None:
            continue
        enquiry_list.append({"enquiry": enquiry, "business_days": business_days})
        total_business_days += business_days
        valid_count += 1

    avg_days = total_business_days / valid_count if valid_count > 0 else 0
    return enquiry_list, total_business_days, valid_count, avg_days


def _group_by_member(enquiry_list):
    """Group enquiry business-day data by member and compute averages."""
    member_stats = {}
    for item in enquiry_list:
        enquiry = item["enquiry"]
        business_days = item["business_days"]
        member_key = enquiry.member.id

        if member_key not in member_stats:
            member_stats[member_key] = {
                "member": enquiry.member,
                "total_enquiries": 0,
                "total_days": 0,
                "enquiries": [],
            }

        member_stats[member_key]["total_enquiries"] += 1
        member_stats[member_key]["total_days"] += business_days
        member_stats[member_key]["enquiries"].append(
            {"enquiry": enquiry, "response_days": business_days}
        )

    for stats in member_stats.values():
        stats["avg_days"] = (
            stats["total_days"] / stats["total_enquiries"]
            if stats["total_enquiries"] > 0
            else 0
        )
    return member_stats


def _build_date_filter_q(date_from, date_to, service_type, prefix="enquiries"):
    """Build a Q object for date range and service type filtering."""
    date_filter = Q()
    if date_from:
        date_filter &= Q(**{f"{prefix}__created_at__gte": date_from})
    if date_to:
        date_filter &= Q(**{f"{prefix}__created_at__lte": date_to})
    if service_type:
        date_filter &= Q(**{f"{prefix}__service_type": service_type})
    return date_filter


def _build_status_filters(count_filter, prefix="enquiries"):
    """Build open and closed Q filters based on a base count filter."""
    open_filter = count_filter & Q(**{f"{prefix}__status__in": ["new", "open"]})
    closed_filter = count_filter & Q(**{f"{prefix}__status": "closed"})
    return open_filter, closed_filter


def _annotate_with_enquiry_counts(
    queryset, count_filter, has_date_range, prefix="enquiries"
):
    """Annotate a queryset with total, open, and closed enquiry counts."""
    base_filter = count_filter if has_date_range else Q()
    open_filter, closed_filter = _build_status_filters(
        count_filter if has_date_range else Q(), prefix=prefix
    )

    return queryset.annotate(
        total_enquiries=Count(prefix, filter=base_filter),
        open_enquiries=Count(prefix, filter=open_filter),
        closed_enquiries=Count(prefix, filter=closed_filter),
    )


def _calculate_system_totals(date_from, date_to, service_type, section=None):
    """Calculate system-wide or section-specific enquiry totals."""
    qs = Enquiry.objects.all()
    if section:
        qs = qs.filter(section=section)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    if service_type:
        qs = qs.filter(service_type=service_type)
    return (
        qs.count(),
        qs.filter(status__in=["new", "open"]).count(),
        qs.filter(status="closed").count(),
    )


def _get_default_section(date_filter, date_from, date_to):
    """Get the most active section when none is specified."""
    section_query = Section.objects
    if date_from or date_to:
        section_query = section_query.filter(date_filter)

    return (
        section_query.annotate(
            total_enquiries=Count(
                "enquiries", filter=date_filter if (date_from or date_to) else Q()
            )
        )
        .order_by("-total_enquiries")
        .first()
    )


def _build_job_type_query(count_filter, section=None):
    """Build annotated job type query for workload charts."""
    job_type_filter = Q()
    if section:
        job_type_filter = Q(enquiries__section=section)

    combined_filter = job_type_filter & count_filter

    open_filter = combined_filter & Q(enquiries__status__in=["new", "open"])
    closed_filter = combined_filter & Q(enquiries__status="closed")

    qs = (
        JobType.objects.filter(combined_filter)
        .annotate(
            total_enquiries=Count("enquiries", filter=combined_filter),
            open_enquiries=Count("enquiries", filter=open_filter),
            closed_enquiries=Count("enquiries", filter=closed_filter),
        )
        .order_by("-total_enquiries")
    )
    return qs


def _classify_enquiry_for_sla(
    enquiry, section_data, section_id, section_name, section_obj
):
    """Classify an enquiry as within/outside SLA or still open, updating section_data."""
    from .utils import calculate_business_days

    if section_id not in section_data:
        section_data[section_id] = {
            "id": section_id,
            "name": section_name,
            "section": section_obj,
            "enquiries_within_sla": 0,
            "enquiries_outside_sla": 0,
            "enquiries_open": 0,
        }

    if enquiry.status == "closed" and enquiry.closed_at:
        business_days_to_close = calculate_business_days(
            enquiry.created_at, enquiry.closed_at
        )
        if (
            business_days_to_close is not None
            and business_days_to_close <= settings.ENQUIRY_SLA_DAYS
        ):
            section_data[section_id]["enquiries_within_sla"] += 1
        else:
            section_data[section_id]["enquiries_outside_sla"] += 1
    elif enquiry.status in ["new", "open"]:
        section_data[section_id]["enquiries_open"] += 1


def _filter_active_sections(section_data):
    """Filter section data to only include sections with at least one enquiry."""
    sections = []
    for data in section_data.values():
        has_enquiries = (
            data["enquiries_within_sla"] > 0
            or data["enquiries_outside_sla"] > 0
            or data["enquiries_open"] > 0
        )
        if has_enquiries:
            sections.append(data)
    sections.sort(key=lambda x: x["name"] or "ZZZ")
    return sections


## DO NOT DELETE THE VIEWS IN THIS SECTION -----------------------------------------------


@require_http_methods(["GET"])
def welcome(request):
    """Landing page for unauthenticated users."""
    if request.user.is_authenticated:
        return redirect(URL_ENQUIRY_LIST)
    return render(request, "welcome.html")


@login_required
@require_http_methods(["GET"])
def index(request):
    """Home page view - Members Enquiries Dashboard."""

    # Get recent enquiries for dashboard
    recent_enquiries = Enquiry.objects.select_related(
        "admin", "member", "section"
    ).order_by("-created_at")[:5]

    # Count enquiries by status - combine 'new' and 'open' as 'Open'
    enquiry_counts = {
        "total": Enquiry.objects.count(),
        "open": Enquiry.objects.filter(
            status__in=["new", "open"]
        ).count(),  # Combined count
        "closed": Enquiry.objects.filter(status="closed").count(),
    }

    # Count overdue enquiries using business days (consistent with detailed report)
    from .utils import calculate_business_days

    open_enquiries = Enquiry.objects.filter(status__in=["new", "open"])
    overdue_count = 0

    for enquiry in open_enquiries:
        business_days_since_created = calculate_business_days(
            enquiry.created_at, timezone.now()
        )
        if (
            business_days_since_created is not None
            and business_days_since_created > settings.ENQUIRY_SLA_DAYS
        ):
            overdue_count += 1

    context = {
        "recent_enquiries": recent_enquiries,
        "enquiry_counts": enquiry_counts,
        "overdue_count": overdue_count,
        "today": timezone.now().date(),
    }
    return render(request, "index.html", context)


@login_required
@require_http_methods(["POST"])
def logout_view(request):
    """Custom logout view."""
    logout(request)
    MessageService.success(request, "You have been logged out successfully.")
    return redirect("application:welcome")


## DO NOT DELETE THE VIEWS ABOVE - THEY ARE NEEDED FOR THE APP TO WORK ## ----------------


# Enquiry Creation Views and APIs


@login_required
@require_http_methods(["GET"])
def api_find_member_by_email(request):
    """API endpoint to find a member by email address."""
    email = request.GET.get("email", "").strip()
    if not email:
        return MessageService.create_error_response("No email provided")

    try:
        # Use unified email service for member lookup
        member = UnifiedEmailService.find_member_by_email(email)
        if member:
            return MessageService.create_success_response(
                data={
                    "member": {
                        "id": member.id,
                        "name": member.full_name,
                        "email": member.email,
                        "ward": member.ward.name if member.ward else "Unknown",
                    }
                }
            )
        else:
            return MessageService.create_error_response(
                f"No active member found with email: {email}"
            )
    except Exception as e:
        logger.error(f"Error finding member by email: {e}", exc_info=True)
        return MessageService.create_error_response(
            "Error occurred while searching for member"
        )


@login_required
@admin_required()
@require_http_methods(["GET", "POST"])
def enquiry_create(request):
    """Create a new enquiry."""

    if request.method == "POST":
        form = StaffEnquiryForm(request.POST)
        if form.is_valid():
            # Use service to handle complex creation logic
            enquiry = EnquiryService.create_enquiry_with_attachments(
                form_data=form.cleaned_data,
                user=request.user,
                extracted_images_json=request.POST.get("extracted_images", ""),
            )

            MessageService.success(
                request, f'Enquiry "{enquiry.reference}" created successfully.'
            )
            return redirect(URL_ENQUIRY_DETAIL, pk=enquiry.pk)
    else:
        form = StaffEnquiryForm()

    return render(
        request, "enquiry_form.html", {"form": form, "title": "Create Enquiry"}
    )


@login_required
@require_http_methods(["GET", "POST"])
def enquiry_edit(request, pk):
    """Edit an existing enquiry."""
    enquiry, error_redirect = _get_enquiry_or_redirect(pk, request)
    if error_redirect:
        return error_redirect

    # Prevent editing of closed enquiries
    if enquiry.status == "closed":
        messages.warning(
            request, f'Cannot edit enquiry "{enquiry.reference}" because it is closed.'
        )
        return redirect(URL_ENQUIRY_DETAIL, pk=enquiry.pk)

    if request.method == "POST":
        attach_only = request.POST.get("attach_only", False)
        extracted_images_json = request.POST.get("extracted_images", "")

        if attach_only and extracted_images_json:
            return _handle_attach_only_request(
                enquiry, request.user, extracted_images_json
            )

        form = StaffEnquiryForm(request.POST, instance=enquiry)
        result = _handle_enquiry_edit_post(
            request, enquiry, form, extracted_images_json
        )
        if result is not None:
            return result
    else:
        form = StaffEnquiryForm(instance=enquiry)

    # Get attachments for this enquiry to display in edit mode
    attachments = enquiry.attachments.select_related("uploaded_by").order_by(
        "-uploaded_at"
    )

    return render(
        request,
        "enquiry_form.html",
        {
            "form": form,
            "enquiry": enquiry,
            "attachments": attachments,
            "title": "Edit Enquiry",
        },
    )


@login_required
@require_http_methods(["POST"])
def enquiry_reopen(request, pk):
    """Re-open a closed enquiry with reason."""
    enquiry, error_redirect = _get_enquiry_or_redirect(pk, request)
    if error_redirect:
        return error_redirect

    # Only allow re-opening of closed enquiries
    if enquiry.status != "closed":
        messages.warning(
            request,
            f'Enquiry "{enquiry.reference}" is not closed and cannot be re-opened.',
        )
        return _redirect_to_referer_or_detail(request, enquiry.pk)

    reason = request.POST.get("reason", "").strip()
    note = request.POST.get("note", "").strip()

    if not reason:
        return _handle_reopen_missing_reason(request, pk)

    # Re-open the enquiry
    enquiry.status = "open"
    enquiry.closed_at = None
    enquiry.save(update_fields=["status", "closed_at"])

    # Create history entry
    history_note = f"Enquiry re-opened by {request.user.get_full_name() or request.user.username}\nReason: {reason}"
    if note:
        history_note += f"\nAdditional notes: {note}"

    EnquiryHistory.objects.create(
        enquiry=enquiry,
        note=history_note,
        note_type="enquiry_reopened",
        created_by=request.user,
    )

    if _is_ajax(request):
        return _build_reopen_ajax_success(enquiry)

    return _handle_reopen_redirect(request, pk, enquiry)


### Email and Attachment functionality


@login_required
@csrf_protect
@require_http_methods(["POST"])
def api_parse_email(request):
    """API endpoint to parse uploaded email files."""
    uploaded_file = request.FILES.get("email_file")
    if not uploaded_file:
        return JsonResponse({"success": False, "error": MSG_NO_FILE_PROVIDED})

    # Use unified email processing service
    return UnifiedEmailService.process_email_for_form_population(uploaded_file)


@login_required
@csrf_protect
@require_http_methods(["POST"])
def api_parse_email_update(request):
    """API endpoint to parse email files for enquiry updates."""
    if "email_file" not in request.FILES:
        return JsonResponse({"success": False, "error": "No email file provided"})

    email_file = request.FILES["email_file"]

    # Use unified email processing service
    return UnifiedEmailService.process_email_for_history(email_file)


@login_required
@csrf_protect
@require_http_methods(["POST"])
def api_upload_photos(request):
    """API endpoint to handle file uploads (images and documents) from email attachments or manual uploads."""
    # Support both 'photo_file' (existing) and 'file' (new dropzone) parameter names
    uploaded_file = request.FILES.get("photo_file") or request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"success": False, "error": MSG_NO_FILE_PROVIDED})

    # Check if this is for attaching to an existing enquiry
    enquiry_id = request.POST.get("enquiry_id")
    enquiry = None
    if enquiry_id:
        try:
            enquiry = Enquiry.objects.get(id=enquiry_id)
        except Enquiry.DoesNotExist:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Enquiry with ID {enquiry_id} does not exist",
                },
                status=404,
            )

    try:
        file_type, error_response = _get_upload_file_type(uploaded_file)
        if error_response:
            return error_response

        result = _handle_file_upload(uploaded_file, file_type)

        if not result["success"]:
            return JsonResponse({"success": False, "error": result["error"]})

        logger.info(
            f"Manual {file_type} upload: {uploaded_file.name} -> {result['file_path']}"
        )

        response_data = _build_upload_response(result, file_type, file_type == "image")

        if enquiry:
            attachment = _create_attachment_for_enquiry(enquiry, result, request)
            response_data.update(
                {
                    "attachment_id": attachment.id,
                    "enquiry_id": enquiry.id,
                    "message": "File attached successfully",
                }
            )

        return JsonResponse({"success": True, "data": response_data})

    except Exception as e:
        logger.error(f"Unexpected error in api_upload_photos: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": f"Error uploading file: {str(e)}"}
        )


@login_required
@csrf_protect
@require_http_methods(["POST"])
def upload_image(request):
    """Handle image uploads for Summernote editor with enhanced security."""
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": MSG_NO_FILE_PROVIDED}, status=400)

    try:
        # Use secure file upload service
        result = FileUploadService.handle_image_upload(uploaded_file, "editor_uploads")

        if result["success"]:
            # Return URL in format expected by Summernote
            return JsonResponse(
                {
                    "url": result["file_url"],
                    "filename": result["saved_filename"],
                    "size": result["file_size"],
                    "original_size": result["original_size"],
                    "was_resized": result["was_resized"],
                }
            )
        else:
            status_code = 400 if result.get("error_type") == "validation" else 500
            return JsonResponse({"error": result["error"]}, status=status_code)

    except Exception as e:
        logger.error(f"Unexpected error in upload_image: {e}", exc_info=True)
        return JsonResponse({"error": f"Error uploading image: {str(e)}"}, status=500)


@login_required
@csrf_protect
@require_http_methods(["POST"])
def api_add_email_note(request, pk):
    """API endpoint to add email note to enquiry history."""
    try:
        enquiry = Enquiry.objects.get(pk=pk)
    except Enquiry.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": f"Enquiry with ID {pk} does not exist"}
        )

    try:
        note_content = request.POST.get("note", "").strip()
        direction = request.POST.get("direction", "UNKNOWN").strip()

        if not note_content:
            return JsonResponse({"success": False, "error": "Note content is required"})

        # Determine note type based on email direction
        if direction == "INCOMING":
            note_type = "email_incoming"
        elif direction == "OUTGOING":
            note_type = "email_outgoing"
        else:
            note_type = "email_update"

        # Create history entry (keep HTML formatting for email notes)
        history_entry = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note=note_content,
            note_type=note_type,
            created_by=request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Email note added successfully",
                "history_id": history_entry.id,
            }
        )

    except Exception as e:
        logger.error(f"Error adding email note: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@csrf_protect
@require_http_methods(["DELETE"])
def api_delete_attachment(request, attachment_id):
    """API endpoint to delete an enquiry attachment."""

    # Add debugging information
    logger.info(f"Attempting to delete attachment with ID: {attachment_id}")

    try:
        attachment = EnquiryAttachment.objects.get(id=attachment_id)
        logger.info(
            f"Found attachment: {attachment.filename} (enquiry: {attachment.enquiry.id})"
        )
    except EnquiryAttachment.DoesNotExist:
        logger.warning(f"Attachment with ID {attachment_id} not found in database")
        return JsonResponse(
            {
                "success": False,
                "error": f"Attachment with ID {attachment_id} does not exist",
            },
            status=404,
        )

    try:
        # Store enquiry reference for history
        enquiry = attachment.enquiry
        filename = attachment.filename
        file_existed = False

        # Delete the file from storage - use secure path joining
        try:
            file_path = safe_file_path_join(settings.MEDIA_ROOT, attachment.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
                file_existed = True
                logger.info(f"Physical file deleted: {file_path}")
            else:
                logger.info(f"Physical file already missing: {file_path}")
        except ValueError as e:
            logger.warning(f"Attempted unsafe file path access: {e}")
            return JsonResponse({"success": False, "error": "Invalid file path"})

        # Delete the database record
        attachment.delete()

        # Create appropriate history entry based on file existence
        if file_existed:
            history_note = f"Attachment deleted: {filename}"
            success_message = "Attachment deleted successfully"
        else:
            history_note = f"Attachment removed from enquiry (file was already missing): {filename}"
            success_message = (
                "Attachment removed from enquiry (file was already missing from server)"
            )

        EnquiryHistory.objects.create(
            enquiry=enquiry,
            note=history_note,
            note_type="attachment_deleted",
            created_by=request.user,
        )

        return create_json_response(True, message=success_message)

    except Exception as e:
        logger.error(f"Error deleting attachment {attachment_id}: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# API Views for AJAX lookups


@login_required
@require_http_methods(["GET"])
def api_get_all_contacts(request):
    """API endpoint to get all contacts with their areas."""
    try:
        # Optimized query - fetch all contacts with areas in one query
        contacts = Contact.objects.prefetch_related("areas").all()

        contacts_with_areas = []
        for contact in contacts:
            areas = list(contact.areas.values_list("name", flat=True))
            contacts_with_areas.append(
                {"id": contact.id, "name": contact.name, "areas": areas}
            )

        return JsonResponse(contacts_with_areas, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_get_contacts_by_job_type(request):
    """Get contacts who handle a specific job type."""
    job_type_id = request.GET.get("job_type_id")
    if not job_type_id:
        return JsonResponse([], safe=False)

    try:
        contacts = (
            Contact.objects.filter(job_types__id=job_type_id)
            .prefetch_related("areas")
            .distinct()
        )

        contacts_data = []
        for contact in contacts:
            areas = list(contact.areas.values_list("name", flat=True))
            contacts_data.append(
                {"id": contact.id, "name": contact.name, "areas": areas}
            )

        return JsonResponse(contacts_data, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_get_all_job_types(request):
    """API endpoint to get all job types."""
    job_types = JobType.objects.all().values("id", "name").order_by("name")
    return JsonResponse(list(job_types), safe=False)


@login_required
@require_http_methods(["GET"])
def api_search_job_types(request):
    """API endpoint to search job types by name."""
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)

    job_types = JobType.objects.filter(name__icontains=query).values("id", "name")[
        :10
    ]  # Limit to 10 results

    return JsonResponse(list(job_types), safe=False)


@login_required
@require_http_methods(["GET"])
def api_get_job_types_by_contact(request):
    """Get job types handled by a specific contact."""
    contact_id = request.GET.get("contact_id")
    if not contact_id:
        return JsonResponse([], safe=False)

    try:
        contact = Contact.objects.prefetch_related("job_types").get(id=contact_id)
        job_types = list(contact.job_types.values("id", "name"))

        return JsonResponse(job_types, safe=False)
    except Contact.DoesNotExist:
        return JsonResponse(
            {"error": f"Contact not found with ID: {contact_id}"}, status=404
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_update_closed_enquiry_job_type(request):
    """
    Update job type for closed enquiry when current type is Miscellaneous.
    Bypasses normal save to preserve status and timestamps.

    Security:
    - Requires authentication
    - Validates enquiry status (must be closed)
    - Validates current job type (must be Miscellaneous)
    - Validates new job type belongs to contact
    - Uses transaction for atomicity
    """
    try:
        data = json.loads(request.body)
        enquiry_id = data.get("enquiry_id")
        job_type_id = data.get("job_type_id")

        if not enquiry_id or not job_type_id:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Missing required parameters: enquiry_id and job_type_id",
                },
                status=400,
            )

        # Fetch enquiry with related objects
        try:
            enquiry = Enquiry.objects.select_related("job_type", "contact").get(
                pk=enquiry_id
            )
        except Enquiry.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": f"Enquiry with ID {enquiry_id} not found"},
                status=404,
            )

        # Validation 1: Enquiry must be closed
        if enquiry.status != "closed":
            return JsonResponse(
                {
                    "success": False,
                    "error": "Only closed enquiries can be updated with this method",
                },
                status=403,
            )

        # Validation 2: Current job type must be Miscellaneous
        if not enquiry.job_type or enquiry.job_type.name != "Miscellaneous":
            return JsonResponse(
                {
                    "success": False,
                    "error": "This feature is only available for enquiries with Miscellaneous job type",
                },
                status=403,
            )

        # Validation 3: Must have a contact assigned
        if not enquiry.contact:
            return JsonResponse(
                {"success": False, "error": "This enquiry has no contact assigned"},
                status=400,
            )

        # Fetch the new job type
        try:
            new_job_type = JobType.objects.get(pk=job_type_id)
        except JobType.DoesNotExist:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Job type with ID {job_type_id} not found",
                },
                status=404,
            )

        # Validation 4: New job type must belong to the contact
        if not enquiry.contact.job_types.filter(pk=job_type_id).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": f'Job type "{new_job_type.name}" is not associated with contact "{enquiry.contact.name}"',
                },
                status=403,
            )

        # Validation 5: Cannot set to same job type
        if new_job_type.id == enquiry.job_type.id:
            return JsonResponse(
                {
                    "success": False,
                    "error": "New job type is the same as current job type",
                },
                status=400,
            )

        old_job_type_name = enquiry.job_type.name

        # Update job type and create history within transaction
        with transaction.atomic():
            # Update ONLY job_type field at database level (bypasses model save)
            # This preserves status, closed_at, and updated_at timestamps
            Enquiry.objects.filter(pk=enquiry.id).update(job_type=new_job_type)

            # Create history entry using bulk_create to bypass EnquiryHistory.save()
            # bulk_create performs direct SQL INSERT and doesn't call model save()
            history_note = (
                f"Job Type changed from '{old_job_type_name}' to '{new_job_type.name}' "
                f"(closed enquiry update)"
            )

            EnquiryHistory.objects.bulk_create(
                [
                    EnquiryHistory(
                        enquiry=enquiry,
                        note_type="enquiry_edited",
                        note=history_note,
                        created_by=request.user,
                        created_at=timezone.now(),
                    )
                ]
            )

        logger.info(
            f"User {request.user.username} updated job type for closed enquiry "
            f"{enquiry.reference} from '{old_job_type_name}' to '{new_job_type.name}'"
        )

        return JsonResponse(
            {
                "success": True,
                "message": f'Job type updated to "{new_job_type.name}"',
                "new_job_type": {"id": new_job_type.id, "name": new_job_type.name},
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Error updating closed enquiry job type: {str(e)}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "An unexpected error occurred"}, status=500
        )


@login_required
@require_http_methods(["GET"])
def api_get_contact_section(request):
    """Get section for a specific contact."""
    contact_id = request.GET.get("contact_id")
    if not contact_id:
        return JsonResponse({"success": False, "error": "No contact ID provided"})

    try:
        contact = Contact.objects.select_related("section").get(id=contact_id)

        return JsonResponse(
            {
                "success": True,
                "section": {"id": contact.section.id, "name": contact.section.name},
            }
        )
    except Contact.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": f"Contact not found with ID: {contact_id}"}
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# Reports Views


@login_required
@require_http_methods(["GET"])
def performance_dashboard_report(request):
    """Performance dashboard with Chart.js visualizations."""
    from .date_utils import (
        parse_request_date_range,
        get_page_title_with_date_range,
        get_date_range_subtitle,
        get_javascript_date_constants,
    )
    from django.utils import timezone

    service_type = request.GET.get("service_type", None)
    date_range_info = parse_request_date_range(request, default_range="12months")
    current_date = timezone.now()

    months_back, current_date = _calculate_months_back_for_dashboard(
        date_range_info.range_type, date_range_info, current_date
    )

    months_data = _collect_month_data(months_back, current_date, service_type)

    context = {
        "months_data": json.dumps(months_data),
        "date_range": date_range_info.range_type,
        "filters": {
            "date_from": date_range_info.date_from_str,
            "date_to": date_range_info.date_to_str,
        },
        "js_date_constants": get_javascript_date_constants(),
        "page_title": get_page_title_with_date_range(
            "Performance Dashboard", date_range_info
        ),
        "page_subtitle": get_date_range_subtitle(date_range_info),
        "service_type": service_type,
    }

    return render(request, "reports/performance_dashboard.html", context)


@login_required
@require_http_methods(["GET"])
def average_response_time_report(request):
    """Report showing average days taken for responses."""
    from .date_utils import (
        parse_request_date_range,
        get_page_title_with_date_range,
        get_date_range_subtitle,
        get_javascript_date_constants,
    )

    member_id = request.GET.get("member")
    service_type = request.GET.get("service_type", None)
    date_range_info = parse_request_date_range(request, default_range="12months")

    # Base queryset for closed enquiries
    enquiries = Enquiry.objects.filter(status="closed", closed_at__isnull=False)
    enquiries = _apply_date_and_member_filters(
        enquiries,
        date_range_info.date_from,
        date_range_info.date_to,
        member_id,
        service_type,
    )
    enquiries = enquiries.select_related("member", "section__department", "admin__user")

    enquiry_list, _, _, overall_avg_days = _calculate_business_days_stats(enquiries)
    member_stats = _group_by_member(enquiry_list)

    context = {
        "overall_avg_days": overall_avg_days,
        "member_stats": member_stats,
        "total_enquiries": enquiries.count(),
        "date_range": date_range_info.range_type,
        "filters": {
            "date_from": date_range_info.date_from_str,
            "date_to": date_range_info.date_to_str,
            "member_id": member_id,
        },
        "members": Member.objects.filter(is_active=True).select_related("ward"),
        "js_date_constants": get_javascript_date_constants(),
        "page_title": get_page_title_with_date_range(
            "Average Response Time", date_range_info
        ),
        "page_subtitle": get_date_range_subtitle(date_range_info),
        "service_type": service_type,
    }

    return render(request, "reports/average_response_time.html", context)


@login_required
@require_http_methods(["GET"])
def overdue_enquiries_report(request):
    """Report showing enquiries that are overdue (past the 5-day deadline)."""

    # Get filter parameters
    member_id = request.GET.get("member")
    section_id = request.GET.get("section")
    job_type_id = request.GET.get("job_type")

    # Get all open enquiries (we'll filter by business days logic)
    enquiries = Enquiry.objects.filter(status__in=["new", "open"]).select_related(
        "member", "section__department", "admin__user", "job_type"
    )

    # Apply filters
    if member_id:
        enquiries = enquiries.filter(member_id=member_id)
    if section_id:
        enquiries = enquiries.filter(section_id=section_id)
    if job_type_id:
        enquiries = enquiries.filter(job_type_id=job_type_id)

    # Calculate business days overdue for each enquiry
    from .utils import calculate_business_days, calculate_working_days_due_date

    enquiry_list = []

    for enquiry in enquiries:
        # Calculate business days since creation
        business_days_since_created = calculate_business_days(
            enquiry.created_at, timezone.now()
        )

        # Calculate due date using business days
        due_date = calculate_working_days_due_date(
            enquiry.created_at, settings.ENQUIRY_SLA_DAYS
        )

        if (
            business_days_since_created is not None
            and business_days_since_created > settings.ENQUIRY_SLA_DAYS
        ):
            business_days_overdue = (
                business_days_since_created - settings.ENQUIRY_SLA_DAYS
            )
            calendar_days_since_created = (timezone.now() - enquiry.created_at).days

            enquiry_list.append(
                {
                    "enquiry": enquiry,
                    "days_overdue": business_days_overdue,
                    "business_days_since_created": business_days_since_created,
                    "days_since_created": calendar_days_since_created,
                    "due_date": due_date,
                }
            )

    # Sort by most overdue first
    enquiry_list.sort(key=lambda x: x["days_overdue"], reverse=True)

    context = {
        "enquiry_list": enquiry_list,
        "total_overdue": len(enquiry_list),
        "filters": {
            "member_id": member_id,
            "section_id": section_id,
            "job_type_id": job_type_id,
        },
        "members": Member.objects.filter(is_active=True).select_related("ward"),
        "sections": Section.objects.select_related("department"),
        "job_types": JobType.objects.all().order_by("name"),
        "overdue_threshold": settings.ENQUIRY_SLA_DAYS,
        "calculation_method": "business_days",
    }

    return render(request, "reports/overdue_enquiries.html", context)


@login_required
@require_http_methods(["GET"])
def section_workload_chart_report(request):
    """Chart showing workload distribution across sections."""
    from .date_utils import (
        parse_request_date_range,
        get_page_title_with_date_range,
        get_date_range_subtitle,
        get_javascript_date_constants,
    )

    service_type = request.GET.get("service_type", None)
    date_range_info = parse_request_date_range(request, default_range="12months")

    date_from = date_range_info.date_from
    date_to = date_range_info.date_to
    has_date_range = bool(date_from or date_to)

    count_filter = _build_date_filter_q(date_from, date_to, service_type)

    # Get sections with their enquiry counts - top 20 for chart
    sections_query = Section.objects
    if has_date_range:
        sections_query = sections_query.filter(count_filter)

    sections_for_chart = _annotate_with_enquiry_counts(
        sections_query, count_filter, has_date_range
    ).order_by("-total_enquiries")[:20]

    # All sections for details table
    sections = _annotate_with_enquiry_counts(
        Section.objects.select_related("department"), count_filter, has_date_range
    ).order_by("-total_enquiries", "department__name", "name")

    # Job type distribution
    job_types_query = JobType.objects
    if has_date_range:
        job_types_query = job_types_query.filter(count_filter)

    job_types = job_types_query.annotate(
        total_enquiries=Count(
            "enquiries", filter=count_filter if has_date_range else Q()
        )
    ).order_by("-total_enquiries")

    system_total, system_open, system_closed = _calculate_system_totals(
        date_from, date_to, service_type
    )

    context = {
        "sections": sections,
        "sections_for_chart": sections_for_chart,
        "date_from": date_from,
        "date_to": date_to,
        "date_range": date_range_info.range_type,
        "date_from_str": date_range_info.date_from_str,
        "date_to_str": date_range_info.date_to_str,
        "page_title": get_page_title_with_date_range(
            "Section Workload", date_range_info
        ),
        "page_subtitle": get_date_range_subtitle(date_range_info),
        "job_types": job_types,
        "system_total_enquiries": system_total,
        "system_open_enquiries": system_open,
        "system_closed_enquiries": system_closed,
        "js_date_constants": get_javascript_date_constants(),
        "filters": {
            "date_from": date_range_info.date_from_str,
            "date_to": date_range_info.date_to_str,
        },
        "service_type": service_type,
    }

    return render(request, "reports/section_workload_chart.html", context)


@login_required
@require_http_methods(["GET"])
def job_workload_chart_report(request):
    """Chart showing workload distribution of job types within a selected section."""
    from .date_utils import (
        parse_request_date_range,
        get_javascript_date_constants,
        get_page_title_with_date_range,
        get_date_range_subtitle,
    )

    date_range_info = parse_request_date_range(request, default_range="12months")
    section_filter = request.GET.get("section", "")
    service_type = request.GET.get("service_type", None)
    date_from = date_range_info.date_from
    date_to = date_range_info.date_to

    all_sections = Section.objects.select_related("department").order_by(
        "department__name", "name"
    )

    show_all_sections = section_filter == "all"
    selected_section = None
    if not show_all_sections and section_filter:
        try:
            selected_section = Section.objects.select_related("department").get(
                id=section_filter
            )
        except (Section.DoesNotExist, ValueError):
            pass

    date_filter = _build_date_filter_q(date_from, date_to, service_type)

    if not show_all_sections and not selected_section:
        selected_section = _get_default_section(date_filter, date_from, date_to)

    # Build count filter and get job types + totals
    count_filter = _build_date_filter_q(date_from, date_to, service_type)
    job_types = []
    system_total = system_open = system_closed = 0

    if show_all_sections:
        job_types = _build_job_type_query(count_filter)
        system_total, system_open, system_closed = _calculate_system_totals(
            date_from, date_to, service_type
        )
    elif selected_section:
        job_types = _build_job_type_query(count_filter, section=selected_section)
        system_total, system_open, system_closed = _calculate_system_totals(
            date_from, date_to, service_type, section=selected_section
        )

    context = {
        "job_types": job_types,
        "all_sections": all_sections,
        "selected_section": selected_section,
        "section_filter": section_filter,
        "show_all_sections": show_all_sections,
        "date_range_info": date_range_info,
        "date_range": date_range_info.range_type,
        "date_from_str": date_range_info.date_from_str,
        "date_to_str": date_range_info.date_to_str,
        "filters": {
            "date_from": date_range_info.date_from_str,
            "date_to": date_range_info.date_to_str,
        },
        "js_date_constants": get_javascript_date_constants(),
        "page_title": get_page_title_with_date_range("Job Workload", date_range_info),
        "page_subtitle": get_date_range_subtitle(date_range_info),
        "system_total_enquiries": system_total,
        "system_open_enquiries": system_open,
        "system_closed_enquiries": system_closed,
        "service_type": service_type,
    }

    return render(request, "reports/job_workload_chart.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_member_report(request):
    """Report showing enquiry counts per member."""

    # Get filter parameters
    months = int(request.GET.get("months", 12))  # Default to 12 months
    service_type = request.GET.get("service_type", None)

    # Calculate date range - use exactly 365 days for 12 months, starting from 00:00
    days = 365 if months == 12 else months * 30
    date_from_date = date.today() - timedelta(days=days)
    date_from = timezone.make_aware(
        datetime.combine(date_from_date, datetime.min.time())
    )

    # Build filter for queryset
    queryset_filter = Q(enquiries__created_at__gte=date_from)
    if service_type:
        queryset_filter &= Q(enquiries__service_type=service_type)

    members = (
        Member.objects.filter(queryset_filter)
        .annotate(enquiry_count=Count("enquiries", filter=queryset_filter))
        .order_by("-enquiry_count")
    )

    total_enquiries = sum(m.enquiry_count for m in members)
    total_members = members.count()
    average_per_member = total_enquiries / total_members if total_members > 0 else 0

    context = {
        "members": members,
        "months": months,
        "date_from": date_from,
        "total_enquiries": total_enquiries,
        "total_members": total_members,
        "average_per_member": average_per_member,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_member.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_member_monthly_report(request):
    """Report showing enquiry counts per member across the last 12 months."""
    # Get filter parameters
    service_type = request.GET.get("service_type", None)

    # Generate last 12 months using utility function
    months, month_keys = generate_last_months(12)

    # Calculate overall date range
    date_from, date_to = calculate_month_range_from_keys(month_keys)
    if not date_from:
        date_from = date_to = timezone.now()

    # OPTIMIZED: Single query with aggregation instead of 720 individual queries
    from django.db.models import Count, Case, When, IntegerField

    # Build dynamic aggregation for each month
    month_annotations = {}
    for i, month_key in enumerate(month_keys):
        year, month = month_key.split("-")
        month_start = timezone.make_aware(datetime(int(year), int(month), 1))
        if int(month) == 12:
            month_end = timezone.make_aware(datetime(int(year) + 1, 1, 1))
        else:
            month_end = timezone.make_aware(datetime(int(year), int(month) + 1, 1))

        # Create annotation for this month with service_type filter
        month_filter = Q(
            enquiries__created_at__gte=month_start,
            enquiries__created_at__lt=month_end,
        )
        if service_type:
            month_filter &= Q(enquiries__service_type=service_type)

        month_annotations[f'count_{month_key.replace("-", "_")}'] = Count(
            "enquiries",
            filter=month_filter,
        )

    # Build filter for total count
    total_filter = Q(
        enquiries__created_at__gte=date_from,
        enquiries__created_at__lt=date_to,
    )
    if service_type:
        total_filter &= Q(enquiries__service_type=service_type)

    # Single query to get all members with their monthly counts
    # Match yearly report logic - include both active and inactive members
    members_with_counts = (
        Member.objects.select_related("ward")
        .annotate(
            **month_annotations,
            total_count=Count(
                "enquiries",
                filter=total_filter,
            ),
        )
        .filter(total_count__gt=0)
        .order_by("first_name", "last_name")
    )

    # Build data structure for template
    member_data = []
    for member in members_with_counts:
        member_row = {
            "id": member.id,
            "name": member.full_name,
            "ward": member.ward.name if member.ward else "No Ward",
            "total": member.total_count,
        }

        # Add monthly counts to the row
        for i, month_key in enumerate(month_keys):
            count_attr = f'count_{month_key.replace("-", "_")}'
            member_row[months[i]] = getattr(member, count_attr, 0)

        member_data.append(member_row)

    # Adjust end date for display purposes (last day of last month)
    if date_to:
        date_to = date_to - timedelta(days=1)

    context = {
        "data": member_data,
        "months": months,
        "month_keys": month_keys,
        "total_members": len(member_data),
        "date_from": date_from,
        "date_to": date_to,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_member_monthly.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_section_report(request):
    """Report showing enquiry counts per section."""

    # Get filter parameters
    months = int(request.GET.get("months", 12))  # Default to 12 months
    service_type = request.GET.get("service_type", None)

    # Calculate date range - use exactly 365 days for 12 months, starting from 00:00
    days = 365 if months == 12 else months * 30
    date_from_date = date.today() - timedelta(days=days)
    date_from = timezone.make_aware(
        datetime.combine(date_from_date, datetime.min.time())
    )

    # Build filter for queryset
    queryset_filter = Q(enquiries__created_at__gte=date_from)
    if service_type:
        queryset_filter &= Q(enquiries__service_type=service_type)

    sections = (
        Section.objects.filter(queryset_filter)
        .annotate(enquiry_count=Count("enquiries", filter=queryset_filter))
        .order_by("-enquiry_count")
        .select_related("department")
    )

    total_enquiries = sum(s.enquiry_count for s in sections)
    total_sections = sections.count()
    average_per_section = total_enquiries / total_sections if total_sections > 0 else 0

    context = {
        "sections": sections,
        "months": months,
        "date_from": date_from,
        "total_enquiries": total_enquiries,
        "total_sections": total_sections,
        "average_per_section": average_per_section,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_section.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_section_monthly_report(request):
    """Report showing enquiry counts per section across the last 12 months."""
    # Get filter parameters
    service_type = request.GET.get("service_type", None)

    # Generate last 12 months using utility function
    months, month_keys = generate_last_months(12)

    # Calculate overall date range
    date_from, date_to = calculate_month_range_from_keys(month_keys)
    if not date_from:
        date_from = date_to = timezone.now()

    # OPTIMIZED: Single query with aggregation instead of individual queries per section per month
    from django.db.models import Count

    # Build dynamic aggregation for each month
    month_annotations = {}
    for i, month_key in enumerate(month_keys):
        year, month = month_key.split("-")
        month_start = timezone.make_aware(datetime(int(year), int(month), 1))
        if int(month) == 12:
            month_end = timezone.make_aware(datetime(int(year) + 1, 1, 1))
        else:
            month_end = timezone.make_aware(datetime(int(year), int(month) + 1, 1))

        # Create annotation for this month with service_type filter
        month_filter = Q(
            enquiries__created_at__gte=month_start,
            enquiries__created_at__lt=month_end,
        )
        if service_type:
            month_filter &= Q(enquiries__service_type=service_type)

        month_annotations[f'count_{month_key.replace("-", "_")}'] = Count(
            "enquiries",
            filter=month_filter,
        )

    # Build filter for total count
    total_filter = Q(
        enquiries__created_at__gte=date_from,
        enquiries__created_at__lt=date_to,
    )
    if service_type:
        total_filter &= Q(enquiries__service_type=service_type)

    # Single query to get all sections with their monthly counts
    sections_with_counts = (
        Section.objects.select_related("department")
        .annotate(
            **month_annotations,
            total_count=Count(
                "enquiries",
                filter=total_filter,
            ),
        )
        .filter(total_count__gt=0)
        .order_by("department__name", "name")
    )

    # Build data structure for template
    section_data = []
    for section in sections_with_counts:
        section_row = {
            "id": section.id,
            "name": section.name,
            "department": (
                section.department.name if section.department else "No Department"
            ),
            "total": section.total_count,
        }

        # Add monthly counts to the row
        for i, month_key in enumerate(month_keys):
            count_attr = f'count_{month_key.replace("-", "_")}'
            section_row[months[i]] = getattr(section, count_attr, 0)

        section_data.append(section_row)

    # Sort by total enquiries (descending) - most active sections first
    section_data.sort(key=lambda x: x["total"], reverse=True)

    # Adjust end date for display purposes (last day of last month)
    if date_to:
        date_to = date_to - timedelta(days=1)

    context = {
        "data": section_data,
        "months": months,
        "month_keys": month_keys,
        "total_sections": len(section_data),
        "date_from": date_from,
        "date_to": date_to,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_section_monthly.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_job_report(request):
    """Report showing enquiry counts per job type."""

    # Get filter parameters
    months = int(request.GET.get("months", 12))  # Default to 12 months
    service_type = request.GET.get("service_type", None)

    # Calculate date range - use exactly 365 days for 12 months, starting from 00:00
    days = 365 if months == 12 else months * 30
    date_from_date = date.today() - timedelta(days=days)
    date_from = timezone.make_aware(
        datetime.combine(date_from_date, datetime.min.time())
    )

    # Build filter for queryset
    queryset_filter = Q(enquiries__created_at__gte=date_from)
    if service_type:
        queryset_filter &= Q(enquiries__service_type=service_type)

    job_types = (
        JobType.objects.filter(queryset_filter)
        .annotate(enquiry_count=Count("enquiries", filter=queryset_filter))
        .order_by("-enquiry_count")
    )

    total_enquiries = sum(j.enquiry_count for j in job_types)
    total_job_types = job_types.count()
    average_per_job_type = (
        total_enquiries / total_job_types if total_job_types > 0 else 0
    )

    context = {
        "job_types": job_types,
        "months": months,
        "date_from": date_from,
        "total_enquiries": total_enquiries,
        "total_job_types": total_job_types,
        "average_per_job_type": average_per_job_type,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_job.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_job_monthly_report(request):
    """Report showing enquiry counts per job type across the last 12 months."""
    # Get filter parameters
    service_type = request.GET.get("service_type", None)

    # Generate last 12 months using utility function
    months, month_keys = generate_last_months(12)

    # Calculate overall date range
    date_from, date_to = calculate_month_range_from_keys(month_keys)
    if not date_from:
        date_from = date_to = timezone.now()

    # OPTIMIZED: Single query with aggregation instead of individual queries per job type per month
    from django.db.models import Count

    # Build dynamic aggregation for each month
    month_annotations = {}
    for i, month_key in enumerate(month_keys):
        year, month = month_key.split("-")
        month_start = timezone.make_aware(datetime(int(year), int(month), 1))
        if int(month) == 12:
            month_end = timezone.make_aware(datetime(int(year) + 1, 1, 1))
        else:
            month_end = timezone.make_aware(datetime(int(year), int(month) + 1, 1))

        # Create annotation for this month with service_type filter
        month_filter = Q(
            enquiries__created_at__gte=month_start,
            enquiries__created_at__lt=month_end,
        )
        if service_type:
            month_filter &= Q(enquiries__service_type=service_type)

        month_annotations[f'count_{month_key.replace("-", "_")}'] = Count(
            "enquiries",
            filter=month_filter,
        )

    # Build filter for total count
    total_filter = Q(
        enquiries__created_at__gte=date_from,
        enquiries__created_at__lt=date_to,
    )
    if service_type:
        total_filter &= Q(enquiries__service_type=service_type)

    # Single query to get all job types with their monthly counts
    job_types_with_counts = (
        JobType.objects.annotate(
            **month_annotations,
            total_count=Count(
                "enquiries",
                filter=total_filter,
            ),
        )
        .filter(total_count__gt=0)
        .order_by("name")
    )

    # Build data structure for template
    job_type_data = []
    for job_type in job_types_with_counts:
        job_type_row = {
            "id": job_type.id,
            "name": job_type.name,
            "total": job_type.total_count,
        }

        # Add monthly counts to the row
        for i, month_key in enumerate(month_keys):
            count_attr = f'count_{month_key.replace("-", "_")}'
            job_type_row[months[i]] = getattr(job_type, count_attr, 0)

        job_type_data.append(job_type_row)

    # Sort by total enquiries (descending) - most active job types first
    job_type_data.sort(key=lambda x: x["total"], reverse=True)

    # Adjust end date for display purposes (last day of last month)
    if date_to:
        date_to = date_to - timedelta(days=1)

    context = {
        "data": job_type_data,
        "months": months,
        "month_keys": month_keys,
        "total_job_types": len(job_type_data),
        "date_from": date_from,
        "date_to": date_to,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_job_monthly.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_ward_report(request):
    """Report showing enquiry counts per ward."""

    # Get filter parameters
    months = int(request.GET.get("months", 12))  # Default to 12 months
    service_type = request.GET.get("service_type", None)

    # Calculate date range - use exactly 365 days for 12 months, starting from 00:00
    days = 365 if months == 12 else months * 30
    date_from_date = date.today() - timedelta(days=days)
    date_from = timezone.make_aware(
        datetime.combine(date_from_date, datetime.min.time())
    )

    # Build filter for queryset
    queryset_filter = Q(members__enquiries__created_at__gte=date_from)
    if service_type:
        queryset_filter &= Q(members__enquiries__service_type=service_type)

    wards = (
        Ward.objects.filter(queryset_filter)
        .annotate(
            enquiry_count=Count(
                "members__enquiries",
                filter=queryset_filter,
            )
        )
        .order_by("-enquiry_count")
    )

    total_enquiries = sum(w.enquiry_count for w in wards)
    total_wards = wards.count()
    average_per_ward = total_enquiries / total_wards if total_wards > 0 else 0

    context = {
        "wards": wards,
        "months": months,
        "date_from": date_from,
        "total_enquiries": total_enquiries,
        "total_wards": total_wards,
        "average_per_ward": average_per_ward,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_ward.html", context)


@login_required
@require_http_methods(["GET"])
def enquiries_per_ward_monthly_report(request):
    """Report showing enquiry counts per ward across the last 12 months."""
    # Get filter parameters
    service_type = request.GET.get("service_type", None)

    # Generate last 12 months using utility function
    months, month_keys = generate_last_months(12)

    # Calculate overall date range
    date_from, date_to = calculate_month_range_from_keys(month_keys)
    if not date_from:
        date_from = date_to = timezone.now()

    # OPTIMIZED: Single query with aggregation instead of individual queries per ward per month
    from django.db.models import Count

    # Build dynamic aggregation for each month
    month_annotations = {}
    for i, month_key in enumerate(month_keys):
        year, month = month_key.split("-")
        month_start = timezone.make_aware(datetime(int(year), int(month), 1))
        if int(month) == 12:
            month_end = timezone.make_aware(datetime(int(year) + 1, 1, 1))
        else:
            month_end = timezone.make_aware(datetime(int(year), int(month) + 1, 1))

        # Create annotation for this month with service_type filter
        month_filter = Q(
            members__enquiries__created_at__gte=month_start,
            members__enquiries__created_at__lt=month_end,
        )
        if service_type:
            month_filter &= Q(members__enquiries__service_type=service_type)

        month_annotations[f'count_{month_key.replace("-", "_")}'] = Count(
            "members__enquiries",
            filter=month_filter,
        )

    # Build filter for total count
    total_filter = Q(
        members__enquiries__created_at__gte=date_from,
        members__enquiries__created_at__lt=date_to,
    )
    if service_type:
        total_filter &= Q(members__enquiries__service_type=service_type)

    # Single query to get all wards with their monthly counts
    wards_with_counts = (
        Ward.objects.annotate(
            **month_annotations,
            total_count=Count(
                "members__enquiries",
                filter=total_filter,
            ),
        )
        .filter(total_count__gt=0)
        .order_by("name")
    )

    # Build data structure for template
    ward_data = []
    grand_totals = [0] * 12  # Initialize totals for each month

    for ward in wards_with_counts:
        ward_months = []

        # Get monthly counts and build months array
        for i, month_key in enumerate(month_keys):
            count_attr = f'count_{month_key.replace("-", "_")}'
            count = getattr(ward, count_attr, 0)
            ward_months.append(count)
            grand_totals[i] += count

        ward_row = {
            "id": ward.id,
            "name": ward.name,
            "months": ward_months,
            "total": ward.total_count,
        }
        ward_data.append(ward_row)

    # Sort by total enquiries (descending) - most active wards first
    ward_data.sort(key=lambda x: x["total"], reverse=True)

    # Calculate totals
    total_enquiries = sum(grand_totals)
    total_wards = len(ward_data)

    # Adjust end date for display purposes (last day of last month)
    if date_to:
        date_to = date_to - timedelta(days=1)

    context = {
        "ward_data": ward_data,
        "months": months,
        "month_keys": month_keys,
        "grand_totals": grand_totals,
        "total_enquiries": total_enquiries,
        "total_wards": total_wards,
        "date_from": date_from,
        "date_to": date_to,
        "service_type": service_type,
    }

    return render(request, "reports/enquiries_per_ward_monthly.html", context)


@login_required
@require_http_methods(["GET"])
def monthly_enquiries_report(request):
    """Report showing enquiry SLA performance by month and section."""
    import calendar

    selected_month = request.GET.get("month", timezone.now().strftime("%Y-%m"))

    try:
        year, month = map(int, selected_month.split("-"))
        selected_date = timezone.make_aware(datetime(year, month, 1))
    except (ValueError, TypeError):
        selected_date = timezone.now().replace(day=1)
        year = selected_date.year
        month = selected_date.month
        selected_month = selected_date.strftime("%Y-%m")

    month_start = selected_date.replace(day=1)
    month_end = (
        month_start.replace(year=year + 1, month=1)
        if month == 12
        else month_start.replace(month=month + 1)
    )
    month_end_date = selected_date.replace(day=calendar.monthrange(year, month)[1])

    # Generate list of months for dropdown (last 24 months)
    months_list = []
    current_date = timezone.now().replace(day=1)
    for i in range(24):
        month_date = (current_date - timedelta(days=i * 30)).replace(day=1)
        months_list.append(month_date)

    # Get all enquiries for the month and classify by section
    month_enquiries = Enquiry.objects.filter(
        created_at__gte=month_start, created_at__lt=month_end
    ).select_related("section")

    section_data = {}
    for enquiry in month_enquiries:
        sec_id = enquiry.section.id if enquiry.section else None
        sec_name = enquiry.section.name if enquiry.section else "Unassigned"
        _classify_enquiry_for_sla(
            enquiry, section_data, sec_id, sec_name, enquiry.section
        )

    sections = _filter_active_sections(section_data)

    context = {
        "sections": sections,
        "months": months_list,
        "selected_month": selected_month,
        "selected_month_name": selected_date.strftime("%B %Y"),
        "month_start": month_start,
        "month_end": month_end,
        "month_end_date": month_end_date,
    }

    return render(request, "reports/enquiries_per_month.html", context)


# Legacy Report Views - Redirect to enquiry_list


@login_required
@require_http_methods(["GET"])
def enquiries_by_section(request, section_id):
    """Redirect to main enquiries list with section filter."""

    # Redirect to main enquiries list with section filter
    params = {"section": section_id}
    url = reverse(URL_ENQUIRY_LIST) + "?" + urlencode(params)
    return HttpResponseRedirect(url)


@login_required
@require_http_methods(["GET"])
def enquiries_by_contact(request, contact_id):
    """Redirect to main enquiries list with contact filter."""

    # Redirect to main enquiries list with contact filter
    params = {"contact": contact_id}
    url = reverse(URL_ENQUIRY_LIST) + "?" + urlencode(params)
    return HttpResponseRedirect(url)


@login_required
@require_http_methods(["GET"])
def enquiries_by_jobtype(request, jobtype_id):
    """Redirect to main enquiries list with job type filter."""

    # Redirect to main enquiries list with job type filter
    params = {"job_type": jobtype_id}
    url = reverse(URL_ENQUIRY_LIST) + "?" + urlencode(params)
    return HttpResponseRedirect(url)
