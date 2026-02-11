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

import os

from django.contrib import admin
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import path
from django.template.response import TemplateResponse
from django.db import transaction
from django.db.models import ProtectedError
from .models import (
    Admin,
    Area,
    Department,
    Section,
    Ward,
    Member,
    JobType,
    Enquiry,
    EnquiryHistory,
    Audit,
    Contact,
    EnquiryAttachment,
    UserMapping,
)

# ---------------------------------------------------------------------------
# Shared helpers for merge actions
# ---------------------------------------------------------------------------

# Image file extensions that can be resized
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}


def _format_protected_object(obj):
    """Format a single protected object for error display."""
    if hasattr(obj, "_meta"):
        model_name = obj._meta.verbose_name
        if hasattr(obj, "pk"):
            return f"{model_name} (ID: {obj.pk})"
    return str(obj)


def _collect_protected_objects(protected_objects_set):
    """Collect formatted descriptions of protected objects from a ProtectedError."""
    result = []
    for obj in protected_objects_set:
        if hasattr(obj, "__len__") and not isinstance(obj, str):
            result.extend(_format_protected_object(item) for item in obj)
        else:
            result.append(_format_protected_object(obj))
    return result


def _report_protected_error(request, e, entity_name, entity_id):
    """Report a ProtectedError to the user via admin messages."""
    protected_objects = _collect_protected_objects(e.protected_objects)
    suffix = "..." if len(protected_objects) > 5 else ""
    messages.error(
        request,
        f'Cannot delete "{entity_name}" (ID: {entity_id}). '
        f'Protected by: {", ".join(protected_objects[:5])}{suffix}. '
        f"Please check for additional references in the database.",
    )


def _validate_merge_selection(request, queryset, entity_label):
    """Validate that exactly 2 items are selected for merge.

    Returns the ordered list of items or None if validation fails.
    """
    items = list(queryset.order_by("id"))
    if len(items) != 2:
        messages.error(
            request,
            f"Please select exactly 2 {entity_label} to merge. "
            "Multiple merges must be done one at a time to prevent accidents.",
        )
        return None
    return items


def _delete_duplicate_and_report(request, duplicate, primary_name_func):
    """Delete the duplicate record and report success.

    Returns (duplicate_name, duplicate_id) on success or None on ProtectedError.
    """
    duplicate_name = primary_name_func(duplicate)
    duplicate_id = duplicate.id
    try:
        duplicate.delete()
    except ProtectedError as e:
        _report_protected_error(request, e, duplicate_name, duplicate_id)
        return None
    return duplicate_name, duplicate_id


def _report_merge_success(
    request, duplicate_name, duplicate_id, primary_display, enquiries_moved
):
    """Send success messages after a successful merge."""
    messages.success(
        request,
        f'Merged "{duplicate_name}" (ID: {duplicate_id}) into "{primary_display}"',
    )
    if enquiries_moved > 0:
        messages.success(
            request,
            f'Moved {enquiries_moved} enquiry/enquiries to "{primary_display}".',
        )


def _format_bytes(total_bytes):
    """Format a byte count for human-readable display."""
    if total_bytes > 1024 * 1024 * 1024:
        return f"{total_bytes / (1024 * 1024 * 1024):.1f} GB"
    if total_bytes > 1024 * 1024:
        return f"{total_bytes / (1024 * 1024):.1f} MB"
    return f"{total_bytes / 1024:.1f} KB"


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class EnquiryHistoryInline(admin.TabularInline):
    """Inline admin for Enquiry History."""

    model = EnquiryHistory
    extra = 0
    readonly_fields = ("created_by", "created_at")


# ---------------------------------------------------------------------------
# Admin model registrations
# ---------------------------------------------------------------------------


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    """Admin configuration for Admin model."""

    list_display = ("user", "user_email", "user_full_name")
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    )

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = "Email"

    def user_full_name(self, obj):
        return obj.user.get_full_name()

    user_full_name.short_description = "Full Name"


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------


def apply_user_mappings(modeladmin, request, queryset):
    """Bulk action to apply user mappings to historical enquiries."""
    total_updated = 0
    applied_count = 0

    for mapping in queryset.filter(is_primary_mapping=True, applied_at__isnull=True):
        updated_count = mapping.apply_to_enquiries()
        if updated_count > 0:
            total_updated += updated_count
            applied_count += 1

    if applied_count > 0:
        messages.success(
            request,
            f"Applied {applied_count} mappings, updating {total_updated} records (enquiries, history, attachments).",
        )
    else:
        messages.warning(
            request,
            "No mappings were applied. Make sure mappings are marked as primary and not already applied.",
        )


apply_user_mappings.short_description = "Apply selected user mappings to enquiries"


def make_members_inactive(modeladmin, request, queryset):
    """Bulk action to make selected members inactive."""
    updated_count = queryset.update(is_active=False)
    messages.success(request, f"Successfully made {updated_count} member(s) inactive.")


make_members_inactive.short_description = "Mark selected members as inactive"


def merge_members(modeladmin, request, queryset):
    """Merge exactly 2 members into one, keeping the oldest ID."""
    items = _validate_merge_selection(request, queryset, "members")
    if items is None:
        return

    primary_member, duplicate_member = items

    try:
        with transaction.atomic():
            enquiries_moved = Enquiry.objects.filter(member=duplicate_member).update(
                member=primary_member
            )

            result = _delete_duplicate_and_report(
                request, duplicate_member, lambda m: m.full_name
            )
            if result is None:
                return

            duplicate_name, duplicate_id = result
            primary_display = f"{primary_member.full_name} (ID: {primary_member.id})"
            _report_merge_success(
                request, duplicate_name, duplicate_id, primary_display, enquiries_moved
            )

    except Exception as e:
        messages.error(request, f"Error during member merge: {str(e)}")


merge_members.short_description = "Merge selected members (exactly 2, keep oldest ID)"

# SAFETY FEATURES FOR MEMBER MERGE:
# 1. Exactly 2 members must be selected (prevents accidental bulk merges)
# 2. Always keeps the member with the lowest ID (oldest record)
# 3. Moves all enquiries from duplicate to the primary member
# 4. Uses database transactions for safety
# 5. Detailed error reporting if deletion fails due to other references


def merge_contacts(modeladmin, request, queryset):
    """Merge exactly 2 contacts into one, keeping the oldest ID."""
    items = _validate_merge_selection(request, queryset, "contacts")
    if items is None:
        return

    primary_contact, duplicate_contact = items

    try:
        with transaction.atomic():
            enquiries_moved = Enquiry.objects.filter(contact=duplicate_contact).update(
                contact=primary_contact
            )

            # Merge job_types many-to-many relationship
            for job_type in duplicate_contact.job_types.all():
                primary_contact.job_types.add(job_type)

            result = _delete_duplicate_and_report(
                request, duplicate_contact, lambda c: c.name
            )
            if result is None:
                return

            duplicate_name, duplicate_id = result
            primary_display = f"{primary_contact.name} (ID: {primary_contact.id})"
            _report_merge_success(
                request, duplicate_name, duplicate_id, primary_display, enquiries_moved
            )

    except Exception as e:
        messages.error(request, f"Error during contact merge: {str(e)}")


merge_contacts.short_description = "Merge selected contacts (exactly 2, keep oldest ID)"


def merge_job_types(modeladmin, request, queryset):
    """Merge exactly 2 job types into one, keeping the oldest ID."""
    items = _validate_merge_selection(request, queryset, "job types")
    if items is None:
        return

    primary_job_type, duplicate_job_type = items

    try:
        with transaction.atomic():
            enquiries_moved = Enquiry.objects.filter(
                job_type=duplicate_job_type
            ).update(job_type=primary_job_type)

            contacts_updated = _reassign_contacts_job_type(
                duplicate_job_type, primary_job_type
            )

            result = _delete_duplicate_and_report(
                request, duplicate_job_type, lambda jt: jt.name
            )
            if result is None:
                return

            duplicate_name, duplicate_id = result
            primary_display = f"{primary_job_type.name} (ID: {primary_job_type.id})"
            _report_merge_success(
                request, duplicate_name, duplicate_id, primary_display, enquiries_moved
            )

            if contacts_updated > 0:
                messages.success(
                    request,
                    f'Updated {contacts_updated} contact(s) to reference "{primary_job_type.name}".',
                )

    except Exception as e:
        messages.error(request, f"Error during job type merge: {str(e)}")


merge_job_types.short_description = (
    "Merge selected job types (exactly 2, keep oldest ID)"
)


def _reassign_contacts_job_type(old_job_type, new_job_type):
    """Move contacts from one job type to another, returning the count updated."""
    contacts_with_old = Contact.objects.filter(job_types=old_job_type)
    contacts_updated = 0
    for contact in contacts_with_old:
        contact.job_types.remove(old_job_type)
        contact.job_types.add(new_job_type)
        contacts_updated += 1
    return contacts_updated


def _should_skip_attachment(attachment):
    """Determine whether an attachment should be skipped for resize.

    Returns True if the attachment is not eligible for resizing.
    """
    from django.conf import settings

    _, ext = os.path.splitext(attachment.filename.lower())
    if ext not in IMAGE_EXTENSIONS:
        return True

    file_path = os.path.join(settings.MEDIA_ROOT, attachment.file.name)
    if not os.path.exists(file_path):
        return True

    if os.path.getsize(file_path) <= 2 * 1024 * 1024:
        return True

    return False


def _resize_attachment(attachment):
    """Attempt to resize a single image attachment.

    Returns (space_saved, was_resized). Raises on error.
    """
    from django.conf import settings
    from .utils import _resize_image_if_needed

    file_path = os.path.join(settings.MEDIA_ROOT, attachment.file.name)
    original_size = os.path.getsize(file_path)

    with open(file_path, "rb") as f:
        image_data = f.read()

    processed_data, was_resized, final_size = _resize_image_if_needed(image_data)

    if not was_resized:
        return 0, False

    with open(file_path, "wb") as f:
        f.write(processed_data)

    attachment.file_size = final_size
    attachment.save(update_fields=["file_size"])
    return original_size - final_size, True


def bulk_resize_images(modeladmin, request, queryset):
    """Bulk resize selected image attachments to save disk space."""
    resized_count = 0
    skipped_count = 0
    error_count = 0
    total_space_saved = 0

    for attachment in queryset:
        try:
            if _should_skip_attachment(attachment):
                skipped_count += 1
                continue

            space_saved, was_resized = _resize_attachment(attachment)
            if was_resized:
                total_space_saved += space_saved
                resized_count += 1
            else:
                skipped_count += 1
        except Exception:
            error_count += 1

    _report_resize_results(
        request, resized_count, skipped_count, error_count, total_space_saved
    )


bulk_resize_images.short_description = (
    "Resize selected image attachments (saves disk space)"
)


def _report_resize_results(
    request, resized_count, skipped_count, error_count, total_space_saved
):
    """Build and send result messages for the bulk resize action."""
    result_parts = []
    if resized_count > 0:
        space_display = _format_bytes(total_space_saved)
        result_parts.append(f"Resized {resized_count} images, saved {space_display}")
    if skipped_count > 0:
        result_parts.append(
            f"Skipped {skipped_count} files (non-images or already small)"
        )
    if error_count > 0:
        result_parts.append(f"{error_count} errors occurred")

    if result_parts:
        messages.success(request, " | ".join(result_parts))
    else:
        messages.info(request, "No images were processed.")


# ---------------------------------------------------------------------------
# UserMapping admin
# ---------------------------------------------------------------------------


@admin.register(UserMapping)
class UserMappingAdmin(admin.ModelAdmin):
    """Admin configuration for UserMapping model."""

    list_display = (
        "legacy_user_username",
        "legacy_user_fullname",
        "sso_user",
        "is_primary_mapping",
        "applied_status",
        "created_at",
    )
    list_filter = ("is_primary_mapping", "applied_at", "created_at")
    search_fields = (
        "legacy_user__username",
        "legacy_user__first_name",
        "legacy_user__last_name",
        "sso_user__username",
        "sso_user__first_name",
        "sso_user__last_name",
    )
    readonly_fields = ("created_at", "applied_at")
    actions = [apply_user_mappings]
    raw_id_fields = ("legacy_user", "sso_user")
    change_list_template = "admin/usermapping_change_list.html"

    fieldsets = (
        ("Legacy User Information", {"fields": ("legacy_user", "notes")}),
        ("SSO User Mapping", {"fields": ("sso_user", "is_primary_mapping")}),
        (
            "Application Status",
            {"fields": ("created_at", "applied_at"), "classes": ("collapse",)},
        ),
    )

    def legacy_user_username(self, obj):
        return obj.legacy_user.username

    legacy_user_username.short_description = "Legacy Username"
    legacy_user_username.admin_order_field = "legacy_user__username"

    def legacy_user_fullname(self, obj):
        return obj.legacy_user.get_full_name()

    legacy_user_fullname.short_description = "Legacy Full Name"
    legacy_user_fullname.admin_order_field = "legacy_user__first_name"

    def applied_status(self, obj):
        if obj.applied_at:
            return mark_safe('<span style="color: green;">Applied</span>')
        elif obj.is_primary_mapping:
            return mark_safe('<span style="color: orange;">Pending</span>')
        else:
            return mark_safe('<span style="color: gray;">Secondary</span>')

    applied_status.short_description = "Status"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "migration-wizard/",
                self.admin_site.admin_view(self.migration_wizard_view),
                name="usermapping_migration_wizard",
            ),
        ]
        return custom_urls + urls

    def migration_wizard_view(self, request):
        """Custom view for bulk user migration wizard."""
        if request.method == "POST":
            return self._handle_wizard_post(request)
        return self._render_wizard(request)

    def _handle_wizard_post(self, request):
        """Process POST submission from migration wizard."""
        mappings_created = 0
        for key, value in request.POST.items():
            if not key.startswith("mapping_") or not value:
                continue
            created = self._create_mapping_from_post(key, value)
            if created:
                mappings_created += 1

        if mappings_created > 0:
            messages.success(request, f"Created {mappings_created} user mappings.")
        return redirect("../")

    def _create_mapping_from_post(self, key, value):
        """Create a single user mapping from a POST form field.

        Returns True if a new mapping was created, False otherwise.
        """
        user_id = key.replace("mapping_", "")
        try:
            legacy_user = User.objects.get(id=user_id)
            sso_user = User.objects.get(id=value)
        except User.DoesNotExist:
            return False

        _, created = UserMapping.objects.get_or_create(
            legacy_user=legacy_user,
            sso_user=sso_user,
            defaults={"is_primary_mapping": True},
        )
        return created

    def _render_wizard(self, request):
        """Render the GET view for the migration wizard."""
        context = {
            "legacy_users": self._get_legacy_users_with_enquiries(),
            "sso_users": User.objects.filter(is_active=True).order_by(
                "first_name", "last_name"
            ),
            "existing_mappings": UserMapping.objects.select_related(
                "legacy_user", "sso_user"
            ).all(),
            "title": "User Migration Wizard",
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/user_migration_wizard.html", context)

    def _get_legacy_users_with_enquiries(self):
        """Get legacy users that have enquiries assigned but no SSO mapping."""
        mapped_user_ids = UserMapping.objects.values_list("legacy_user_id", flat=True)

        # Find users who have Admin records with enquiries but aren't mapped yet
        legacy_users = (
            User.objects.filter(admin__assigned_enquiries__isnull=False)
            .exclude(id__in=mapped_user_ids)
            .distinct()
            .order_by("first_name", "last_name")
        )

        return [
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name(),
                "email": user.email,
                "enquiry_count": (
                    user.admin.assigned_enquiries.count()
                    if hasattr(user, "admin")
                    else 0
                ),
            }
            for user in legacy_users
        ]


# ---------------------------------------------------------------------------
# Remaining model admin registrations
# ---------------------------------------------------------------------------


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    """Admin configuration for Area model."""

    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model."""

    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    """Admin configuration for Section model."""

    list_display = ("name", "department")
    list_filter = ("department",)
    search_fields = ("name", "department__name")


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    """Admin configuration for Ward model."""

    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """Admin configuration for Member model."""

    list_display = ("full_name", "email", "ward", "is_active", "enquiry_count")
    list_filter = ("ward", "is_active")
    search_fields = ("first_name", "last_name", "email", "ward__name")
    actions = [make_members_inactive, merge_members]

    def enquiry_count(self, obj):
        """Show the number of enquiries for this member."""
        return obj.enquiries.count()

    enquiry_count.short_description = "Enquiries"

    def get_queryset(self, request):
        """Optimize queryset to include related data."""
        return (
            super()
            .get_queryset(request)
            .select_related("ward")
            .prefetch_related("enquiries")
        )


@admin.register(JobType)
class JobTypeAdmin(admin.ModelAdmin):
    """Admin configuration for JobType model."""

    list_display = ("name", "enquiry_count")
    search_fields = ("name",)
    actions = [merge_job_types]

    def enquiry_count(self, obj):
        """Show the number of enquiries for this job type."""
        return obj.enquiries.count()

    enquiry_count.short_description = "Enquiries"

    def get_queryset(self, request):
        """Optimize queryset to include related data."""
        return super().get_queryset(request).prefetch_related("enquiries")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """Admin configuration for Contact model."""

    list_display = ("name", "section", "email", "telephone_number", "enquiry_count")
    list_filter = ("section", "areas", "job_types")
    search_fields = (
        "name",
        "description",
        "email",
        "telephone_number",
        "section__name",
    )
    filter_horizontal = ("areas", "job_types")
    actions = [merge_contacts]

    def enquiry_count(self, obj):
        """Show the number of enquiries for this contact."""
        return obj.enquiries.count()

    enquiry_count.short_description = "Enquiries"

    def get_queryset(self, request):
        """Optimize queryset to include related data."""
        return (
            super()
            .get_queryset(request)
            .select_related("section")
            .prefetch_related("enquiries", "areas", "job_types")
        )


@admin.register(EnquiryAttachment)
class EnquiryAttachmentAdmin(admin.ModelAdmin):
    """Admin configuration for EnquiryAttachment model."""

    list_display = (
        "filename",
        "enquiry",
        "file_size_display",
        "file_type_display",
        "uploaded_at",
        "uploaded_by",
    )
    list_filter = ("uploaded_at", "uploaded_by")
    search_fields = ("filename", "enquiry__reference", "enquiry__title")
    readonly_fields = ("uploaded_at",)
    raw_id_fields = ("enquiry", "uploaded_by")
    actions = [bulk_resize_images]

    def file_size_display(self, obj):
        """Display file size in human readable format."""
        if obj.file_size:
            if obj.file_size > 1024 * 1024:  # > 1MB
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
            elif obj.file_size > 1024:  # > 1KB
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size} bytes"
        return "Unknown"

    file_size_display.short_description = "File Size"

    def file_type_display(self, obj):
        """Display file type with icon."""
        _, ext = os.path.splitext(obj.filename.lower())

        if ext in IMAGE_EXTENSIONS:
            # Show different icons based on file size for images
            if obj.file_size and obj.file_size > 2 * 1024 * 1024:  # > 2MB
                return mark_safe(
                    f'<span style="color: orange;" title="Large image - can be resized">Image ({ext})</span>'
                )
            else:
                return mark_safe(f'<span style="color: green;">Image ({ext})</span>')
        elif ext in {".pdf"}:
            return mark_safe('<span style="color: blue;">PDF</span>')
        elif ext in {".doc", ".docx"}:
            return mark_safe(f'<span style="color: purple;">Word ({ext})</span>')
        else:
            return mark_safe(f'<span style="color: gray;">Other ({ext})</span>')

    file_type_display.short_description = "Type"


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    """Admin configuration for Enquiry model."""

    list_display = (
        "reference",
        "title",
        "member",
        "status",
        "admin",
        "section",
        "created_at",
        "due_date_display",
    )
    list_filter = ("status", "section", "job_type", "created_at", "member__ward")
    search_fields = (
        "reference",
        "title",
        "description",
        "member__first_name",
        "member__last_name",
    )
    readonly_fields = (
        "reference",
        "created_at",
        "updated_at",
        "closed_at",
        "due_date_display",
    )

    fieldsets = (
        (
            "Enquiry Information",
            {"fields": ("reference", "title", "description", "status")},
        ),
        (
            "Assignment",
            {"fields": ("member", "admin", "section", "contact", "job_type")},
        ),
        (
            "Dates",
            {
                "fields": ("created_at", "updated_at", "closed_at", "due_date_display"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [EnquiryHistoryInline]

    def due_date_display(self, obj):
        return obj.due_date

    due_date_display.short_description = "Due Date"

    def save_model(self, request, obj, form, change):
        if not change and not obj.reference:  # If creating new object without reference
            obj.reference = Enquiry.generate_reference()
        super().save_model(request, obj, form, change)


@admin.register(EnquiryHistory)
class EnquiryHistoryAdmin(admin.ModelAdmin):
    """Admin configuration for Enquiry History model."""

    list_display = ("enquiry", "created_by", "created_at", "note_preview")
    list_filter = ("created_at", "enquiry__status")
    search_fields = (
        "note",
        "enquiry__reference",
        "enquiry__title",
        "created_by__username",
    )
    readonly_fields = ("created_by", "created_at")

    def note_preview(self, obj):
        return obj.note[:50] + "..." if len(obj.note) > 50 else obj.note

    note_preview.short_description = "Note Preview"

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Audit)
class AuditAdmin(admin.ModelAdmin):
    """Admin configuration for Audit model."""

    list_display = (
        "user",
        "action_datetime",
        "enquiry",
        "action_details",
        "ip_address",
    )
    list_filter = ("action_datetime", "user")
    search_fields = (
        "action_details",
        "enquiry__reference",
        "user__username",
        "ip_address",
    )
    readonly_fields = (
        "user",
        "action_datetime",
        "enquiry",
        "action_details",
        "ip_address",
    )

    def has_add_permission(self, request):
        return False  # Audit records should not be manually created

    def has_change_permission(self, request, obj=None):
        return False  # Audit records should not be modified

    def has_delete_permission(self, request, obj=None):
        return False  # Audit records should not be deleted
