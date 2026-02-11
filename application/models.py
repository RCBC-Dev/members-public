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

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.db import transaction


class ReferenceSequence(models.Model):
    """
    Tracks the next available reference number for each year.
    This ensures unique, sequential references even with deletions.
    """

    year = models.IntegerField(unique=True, db_index=True)
    next_number = models.IntegerField(default=1)

    class Meta:
        db_table = "members_app_reference_sequence"

    def __str__(self):
        return f"Year {self.year}: Next #{self.next_number}"

    @classmethod
    def get_next_reference(cls):
        """
        Get the next available reference number for the current year.
        This method is thread-safe and handles race conditions properly.
        """
        current_year = timezone.now().year % 100  # Last two digits
        reference_format = f"MEM-{current_year:02d}-{{:04d}}"

        with transaction.atomic():
            # Get or create the sequence record for this year
            sequence, _ = cls.objects.select_for_update().get_or_create(
                year=current_year, defaults={"next_number": 1}
            )

            # Generate reference and increment counter
            reference_number = sequence.next_number
            new_reference = reference_format.format(reference_number)

            # Double-check uniqueness (should be rare, but handles edge cases)
            while Enquiry.objects.filter(reference=new_reference).exists():
                reference_number += 1
                new_reference = reference_format.format(reference_number)

            # Update the sequence for next time
            sequence.next_number = reference_number + 1
            sequence.save(update_fields=["next_number"])

            return new_reference


class Admin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    class Meta:
        db_table = "members_app_admin"
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        return self.user.get_full_name()


class UserMapping(models.Model):
    """
    Maps legacy Django users to new MS SSO users for data migration.
    Both users exist in the same User table, but we need to transfer Admin/enquiry assignments.
    """

    legacy_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="legacy_mappings_from",
        help_text="Original user (e.g., Kerry who left)",
    )
    sso_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="legacy_mappings_to",
        help_text="New MS SSO user (e.g., 'KM1655')",
    )
    is_primary_mapping = models.BooleanField(
        default=True, help_text="Primary mapping for this legacy user"
    )
    notes = models.TextField(
        blank=True, help_text="Migration notes or comments (e.g., 'User left company')"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this mapping was applied to historical data",
    )

    class Meta:
        db_table = "members_app_user_mapping"
        unique_together = [("legacy_user", "sso_user")]
        indexes = [
            models.Index(fields=["legacy_user"], name="usermapping_legacy_idx"),
            models.Index(fields=["sso_user"], name="usermapping_sso_idx"),
        ]

    def __str__(self):
        primary = " (Primary)" if self.is_primary_mapping else ""
        return f"{self.legacy_user.username} → {self.sso_user.username}{primary}"

    def apply_to_enquiries(self):
        """Apply this mapping to historical enquiry assignments and related data."""
        from django.db import transaction

        if not self.is_primary_mapping:
            return 0  # Only apply primary mappings to avoid conflicts

        with transaction.atomic():
            # Find the legacy admin record (if exists)
            try:
                legacy_admin = Admin.objects.get(user=self.legacy_user)
            except Admin.DoesNotExist:
                legacy_admin = None

            # Get or create new admin object for SSO user
            new_admin, _ = Admin.objects.get_or_create(user=self.sso_user)

            # Update enquiries assigned to legacy admin
            enquiry_count = 0
            if legacy_admin:
                enquiry_count = Enquiry.objects.filter(admin=legacy_admin).update(
                    admin=new_admin
                )

            # Update enquiry history records created by legacy user
            history_count = EnquiryHistory.objects.filter(
                created_by=self.legacy_user
            ).update(created_by=self.sso_user)

            # Update enquiry attachments uploaded by legacy user
            attachment_count = EnquiryAttachment.objects.filter(
                uploaded_by=self.legacy_user
            ).update(uploaded_by=self.sso_user)

            # Update audit records for legacy user
            audit_count = Audit.objects.filter(user=self.legacy_user).update(
                user=self.sso_user
            )

            # Mark as applied if any data was transferred
            total_updates = (
                enquiry_count + history_count + attachment_count + audit_count
            )
            if total_updates > 0:
                self.applied_at = timezone.now()
                self.save(update_fields=["applied_at"])

            return total_updates


class Area(models.Model):
    name = models.CharField(max_length=100, db_index=True, unique=True)
    description = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = "members_app_area"

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=100, db_index=True, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "members_app_department"

    def __str__(self):
        return self.name


class Section(models.Model):
    name = models.CharField(max_length=100, db_index=True, unique=True)
    department = models.ForeignKey(
        Department, related_name="sections", on_delete=models.PROTECT
    )

    class Meta:
        db_table = "members_app_section"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ward(models.Model):
    name = models.CharField(max_length=100, db_index=True, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "members_app_ward"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Member(models.Model):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    ward = models.ForeignKey(Ward, related_name="members", on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "members_app_member"
        ordering = [
            "-is_active",
            "first_name",
            "last_name",
        ]  # Active members first, then alphabetical
        indexes = [
            # Ward + active status for filtering active members by ward
            models.Index(fields=["ward", "is_active"], name="member_ward_active_idx"),
            # Email index for lookups
            models.Index(fields=["email"], name="member_email_idx"),
            # Name indexes for sorting
            models.Index(fields=["first_name", "last_name"], name="member_name_idx"),
        ]

    @property
    def full_name(self):
        """Return the member's full name, similar to User.get_full_name()."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email.split("@")[0]

    def __str__(self):
        return self.full_name


class JobType(models.Model):
    name = models.CharField(max_length=100, db_index=True, unique=True)

    class Meta:
        db_table = "members_app_jobtype"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Enquiry(models.Model):
    STATUS_CHOICES = (
        ("new", "New"),
        ("open", "Open"),
        ("closed", "Closed"),
    )
    SERVICE_TYPE_CHOICES = (
        ("failed_service", "Failed service"),
        ("new_addition", "New/addition requests"),
        ("pre_programmed", "Pre-programmed work"),
        ("3rd_party", "3rd Party"),
    )
    title = models.CharField(max_length=255)
    reference = models.CharField(max_length=12, unique=True, blank=True, null=True)
    description = models.TextField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="open", db_index=True
    )
    member = models.ForeignKey(
        Member, related_name="enquiries", on_delete=models.PROTECT
    )
    admin = models.ForeignKey(
        Admin,
        related_name="assigned_enquiries",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    section = models.ForeignKey(
        Section,
        related_name="enquiries",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    contact = models.ForeignKey(
        "Contact",
        related_name="enquiries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    job_type = models.ForeignKey(
        JobType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enquiries",
    )
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPE_CHOICES,
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        db_table = "members_app_enquiry"
        indexes = [
            # Primary ordering index - most queries order by -created_at
            models.Index(fields=["-created_at"], name="enquiry_created_desc_idx"),
            # Status + created_at compound index for overdue queries
            models.Index(
                fields=["status", "created_at"], name="enquiry_status_created_idx"
            ),
            # Reference prefix index for generate_reference method
            models.Index(fields=["reference"], name="enquiry_reference_idx"),
            # Member + created_at for member-specific queries
            models.Index(
                fields=["member", "-created_at"], name="enquiry_member_created_idx"
            ),
            # Section + created_at for section-specific queries
            models.Index(
                fields=["section", "-created_at"], name="enquiry_section_created_idx"
            ),
            # Admin + created_at for assigned enquiries
            models.Index(
                fields=["admin", "-created_at"], name="enquiry_admin_created_idx"
            ),
            # Contact + created_at for contact-specific queries
            models.Index(
                fields=["contact", "-created_at"], name="enquiry_contact_created_idx"
            ),
            # Updated_at index for recent updates
            models.Index(fields=["-updated_at"], name="enquiry_updated_desc_idx"),
            # Search optimization indexes
            models.Index(fields=["title"], name="enquiry_title_idx"),
            # Job type filtering index
            models.Index(
                fields=["job_type", "-created_at"], name="enquiry_jobtype_created_idx"
            ),
            # Date range filtering indexes
            models.Index(fields=["created_at"], name="enquiry_created_asc_idx"),
            # Compound index for common filter combinations
            models.Index(
                fields=["status", "member", "-created_at"],
                name="enq_status_member_created_idx",
            ),
            models.Index(
                fields=["status", "section", "-created_at"],
                name="enq_status_section_created_idx",
            ),
            # Search performance indexes - for title and reference searches with ordering
            models.Index(fields=["title", "-created_at"], name="enq_title_created_idx"),
            models.Index(
                fields=["reference", "-created_at"], name="enq_ref_created_idx"
            ),
            # Service type filtering index
            models.Index(
                fields=["service_type", "-created_at"], name="enq_service_type_idx"
            ),
            # Ward filtering index - member__ward is accessed via member foreign key
            # This requires an index on Member model for ward + created_at queries
        ]

    def save(self, *args, **kwargs):
        # Auto-assign admin and set status for new enquiries
        if not self.pk:  # New enquiry being created
            # Set status to 'open' if not already set (skip 'new' status in workflow)
            if not self.status:
                self.status = "open"

            # Auto-assign to creating user if they are an admin and no admin is set
            if not self.admin and hasattr(self, "_creating_user"):
                try:
                    admin = Admin.objects.get(user=self._creating_user)
                    self.admin = admin
                except Admin.DoesNotExist:
                    pass  # User is not an admin, leave unassigned

        # Handle closed_at timestamp based on status
        if self.status == "closed" and not self.closed_at:
            # Set closed_at when status changes to closed
            self.closed_at = timezone.now()
        elif self.status != "closed" and self.closed_at:
            # Clear closed_at when status changes from closed to open/new
            self.closed_at = None

        super(Enquiry, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference or 'No Ref'} - {self.title}"

    @property
    def due_date(self):
        """Calculate due date using business days (excluding weekends)."""
        from .utils import calculate_working_days_due_date

        # Use business days calculation for more accurate due dates
        business_due_date = calculate_working_days_due_date(self.created_at, 5)

        if business_due_date:
            # Convert back to datetime with same timezone as created_at
            return timezone.datetime.combine(
                business_due_date, self.created_at.time(), tzinfo=self.created_at.tzinfo
            )
        else:
            # Fallback to calendar days if calculation fails
            return self.created_at + timezone.timedelta(days=5)

    @classmethod
    def generate_reference(cls):
        """
        Generate a unique reference using the ReferenceSequence system.
        This is thread-safe and handles deletions properly.
        """
        return ReferenceSequence.get_next_reference()


class EnquiryHistory(models.Model):
    # Note type choices with corresponding Bootstrap icons
    NOTE_TYPE_CHOICES = [
        ("general", "General Note"),
        ("emailed_member", "Emailed Member"),
        ("emailed_contact", "Emailed Contact"),
        ("phoned_contact", "Phoned Contact"),
        ("chased_contact", "Chased Contact"),
        ("enquiry_created", "Enquiry Created"),
        ("enquiry_edited", "Enquiry Edited"),
        ("attachment_added", "Attachment Added"),
        ("attachment_deleted", "Attachment Deleted"),
        ("enquiry_closed", "Enquiry Closed"),
        ("enquiry_reopened", "Enquiry Reopened"),
        ("email_update", "Email Update"),
        ("email_incoming", "Incoming Email"),
        ("email_outgoing", "Outgoing Email"),
    ]

    enquiry = models.ForeignKey(
        Enquiry, related_name="history", on_delete=models.PROTECT
    )
    note = models.TextField()
    note_type = models.CharField(
        max_length=20, choices=NOTE_TYPE_CHOICES, default="general", db_index=True
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "members_app_enquiryhistory"
        indexes = [
            # Enquiry + created_at for history timeline (most common query)
            models.Index(
                fields=["enquiry", "-created_at"], name="history_enquiry_created_idx"
            ),
            # Note: TextField cannot be indexed in SQL Server, use full-text search instead
        ]

    def save(self, *args, **kwargs):
        # Update the updated_at field of the related Enquiry
        self.enquiry.updated_at = timezone.now()

        # Automatically change status from 'new' to 'open' when history is added
        if self.enquiry.status == "new":
            self.enquiry.status = "open"

        self.enquiry.save(update_fields=["updated_at", "status"])
        super(EnquiryHistory, self).save(*args, **kwargs)

    def get_note_type_icon(self):
        """Return Bootstrap icon class for the note type."""
        icon_map = {
            "general": "bi-chat-text",
            "emailed_member": "bi-envelope-at",
            "emailed_contact": "bi-envelope-check",
            "phoned_contact": "bi-telephone",
            "chased_contact": "bi-telephone-forward",
            "enquiry_created": "bi-plus-circle",
            "enquiry_edited": "bi-pencil",
            "attachment_added": "bi-paperclip",
            "attachment_deleted": "bi-trash",
            "enquiry_closed": "bi-check-circle",
            "enquiry_reopened": "bi-arrow-clockwise",
            "email_update": "bi-envelope-plus",
            "email_incoming": "email-incoming-icon",
            "email_outgoing": "email-outgoing-icon",
        }
        return icon_map.get(self.note_type, "bi-chat-text")

    def get_note_type_color(self):
        """Return Bootstrap color class for the note type."""
        color_map = {
            "general": "text-secondary",
            "emailed_member": "text-primary",
            "emailed_contact": "text-info",
            "phoned_contact": "text-success",
            "chased_contact": "text-warning",
            "enquiry_created": "text-success",
            "enquiry_edited": "text-danger",
            "attachment_added": "text-success",
            "attachment_deleted": "text-danger",
            "enquiry_closed": "text-success",
            "enquiry_reopened": "text-success",
            "email_update": "text-primary",
            "email_incoming": "text-success",
            "email_outgoing": "text-primary",
        }
        return color_map.get(self.note_type, "text-secondary")

    def __str__(self):
        return f"History for {self.enquiry.title} at {self.created_at}"


class Audit(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    action_datetime = models.DateTimeField(auto_now_add=True, db_index=True)
    enquiry = models.ForeignKey(Enquiry, on_delete=models.SET_NULL, null=True)
    action_details = models.CharField(max_length=255)
    ip_address = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "members_app_audit"
        indexes = [
            # User audit trail queries
            models.Index(
                fields=["user", "-action_datetime"], name="audit_user_datetime_idx"
            ),
            # Enquiry audit trail queries
            models.Index(
                fields=["enquiry", "-action_datetime"],
                name="audit_enquiry_datetime_idx",
            ),
        ]


class Contact(models.Model):
    name = models.CharField(max_length=100, db_index=True, unique=True)
    description = models.TextField(blank=True)
    telephone_number = models.CharField(max_length=20)
    email = models.EmailField(
        blank=True, help_text="Contact's email address for enquiry correspondence"
    )
    section = models.ForeignKey(
        Section, related_name="contacts", on_delete=models.PROTECT, db_index=True
    )
    areas = models.ManyToManyField(
        Area, related_name="contacts"
    )  # Changed from wards to areas
    job_types = models.ManyToManyField(
        JobType, related_name="contacts"
    )  # Add this line

    class Meta:
        db_table = "members_app_contact"
        ordering = ["name"]
        indexes = [
            # Filter contacts by section
            models.Index(fields=["section"], name="contact_section_idx"),
        ]

    def clean(self):
        """Validate contact data."""
        super().clean()

        # Additional email validation if email is provided
        if self.email:
            try:
                validate_email(self.email)
            except ValidationError:
                raise ValidationError({"email": "Enter a valid email address."})

            # Ensure email is lowercase for consistency
            self.email = self.email.lower()

    def save(self, *args, **kwargs):
        """Override save to call clean method."""
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class EnquiryAttachment(models.Model):
    """Model to store image attachments linked to enquiries."""

    enquiry = models.ForeignKey(
        Enquiry, related_name="attachments", on_delete=models.CASCADE
    )
    filename = models.CharField(max_length=255)  # Original filename from email
    file_path = models.CharField(max_length=500)  # Relative path from MEDIA_ROOT
    file_size = models.PositiveIntegerField()  # File size in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        db_table = "members_app_enquiryattachment"
        indexes = [
            models.Index(fields=["enquiry", "-uploaded_at"], name="attachment_idx"),
        ]

    def __str__(self):
        return f"{self.filename} - {self.enquiry.reference}"

    @property
    def file_url(self):
        """Return the full URL to access this attachment."""
        from django.conf import settings

        return f"{settings.MEDIA_URL}{self.file_path}"
