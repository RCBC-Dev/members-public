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
Unified Form Styling Service for the Members Enquiries System.

This module consolidates all form styling logic into a single service,
eliminating duplication across forms.py and providing consistent styling.
"""

from typing import Dict, List, Any, Optional, Union
from django import forms
from django.utils import timezone
from datetime import timedelta

from .models import Member, Admin, Section, JobType, Contact, Ward, Enquiry


class FormStyleService:
    """
    Centralized service for all form styling operations.

    This service consolidates functionality from:
    - Repeated Bootstrap class applications in forms.py
    - Widget attribute updates across multiple forms
    - Choice field population patterns
    - Common form field configurations
    """

    # Standard Bootstrap classes for different field types
    BOOTSTRAP_CLASSES = {
        "text": "form-control",
        "textarea": "form-control",
        "email": "form-control",
        "password": "form-control",
        "number": "form-control",
        "date": "form-control",
        "datetime": "form-control",
        "select": "form-select",
        "checkbox": "form-check-input",
        "radio": "form-check-input",
        "file": "form-control",
    }

    # Common placeholder texts
    PLACEHOLDERS = {
        "title": "Brief title for the enquiry",
        "description": "Enter enquiry description...",
        "note": "Add your note or comment about this enquiry...",
        "search": "Search reference, title, or description (powerful search)...",
        "email": "Enter email address...",
        "name": "Enter name...",
    }

    # Common empty labels for select fields
    EMPTY_LABELS = {
        "member": "Select Member...",
        "section": "Select Section (optional)...",
        "contact": "Select Contact...",
        "job_type": "Select Job Type...",
        "admin": "Select Admin...",
        "ward": "Select Ward...",
        "status": "Select Status...",
        "service_type": "Select Service Type...",
    }

    # Filter form empty labels (different from create/edit forms)
    FILTER_EMPTY_LABELS = {
        "member": "All Members",
        "section": "All Sections",
        "contact": "All Contacts",
        "job_type": "All Job Types",
        "admin": "All Admins",
        "ward": "All Wards",
        "status": "All Enquiries",
        "service_type": "All Service Types",
    }

    @classmethod
    def apply_bootstrap_styling(
        cls, form_instance: forms.Form, field_mappings: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Apply Bootstrap styling to form fields automatically.

        Args:
            form_instance: Django form instance
            field_mappings: Optional custom field type mappings
        """
        if field_mappings is None:
            field_mappings = {}

        for field_name, field in form_instance.fields.items():
            # Determine field type
            field_type = cls._get_field_type(field)

            # Use custom mapping if provided, otherwise use default
            bootstrap_class = field_mappings.get(
                field_name, cls.BOOTSTRAP_CLASSES.get(field_type, "form-control")
            )

            # Apply Bootstrap class
            current_class = field.widget.attrs.get("class", "")
            if bootstrap_class not in current_class:
                if current_class:
                    field.widget.attrs["class"] = (
                        f"{current_class} {bootstrap_class}".strip()
                    )
                else:
                    field.widget.attrs["class"] = bootstrap_class

    @classmethod
    def apply_select_field_styling(
        cls,
        form_instance: forms.Form,
        field_names: List[str],
        use_filter_labels: bool = False,
    ) -> None:
        """
        Apply consistent styling to select fields.

        Args:
            form_instance: Django form instance
            field_names: List of field names to style
            use_filter_labels: Whether to use filter labels or create/edit labels
        """
        empty_labels = (
            cls.FILTER_EMPTY_LABELS if use_filter_labels else cls.EMPTY_LABELS
        )

        for field_name in field_names:
            if field_name in form_instance.fields:
                field = form_instance.fields[field_name]

                # Apply Bootstrap class
                field.widget.attrs.update({"class": "form-select"})

                # Set empty label if it's a choice field
                if hasattr(field, "empty_label") and field_name in empty_labels:
                    field.empty_label = empty_labels[field_name]

    @classmethod
    def apply_text_field_styling(
        cls, form_instance: forms.Form, field_configs: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Apply styling to text-based fields with placeholders and other attributes.

        Args:
            form_instance: Django form instance
            field_configs: Dict mapping field names to their configuration
                          e.g., {'title': {'placeholder': 'Enter title', 'maxlength': 100}}
        """
        for field_name, config in field_configs.items():
            if field_name in form_instance.fields:
                field = form_instance.fields[field_name]

                # Apply Bootstrap class
                field.widget.attrs.update({"class": "form-control"})

                # Apply placeholder if specified or use default
                if "placeholder" in config:
                    field.widget.attrs["placeholder"] = config["placeholder"]
                elif field_name in cls.PLACEHOLDERS:
                    field.widget.attrs["placeholder"] = cls.PLACEHOLDERS[field_name]

                # Apply other attributes
                for attr, value in config.items():
                    if attr != "placeholder":
                        field.widget.attrs[attr] = value

    @classmethod
    def populate_choice_fields(
        cls, form_instance: forms.Form, use_filter_labels: bool = False
    ) -> None:
        """
        Populate choice fields with database data using consistent patterns.

        Args:
            form_instance: Django form instance
            use_filter_labels: Whether to use filter labels (All X) or create labels (Select X)
        """
        empty_labels = (
            cls.FILTER_EMPTY_LABELS if use_filter_labels else cls.EMPTY_LABELS
        )

        # Member choices
        if "member" in form_instance.fields:
            form_instance.fields["member"].choices = [
                ("", empty_labels.get("member", "Select Member..."))
            ] + [
                (m.id, f"{m.full_name}{'*' if not m.is_active else ''}")
                for m in Member.objects.all()  # Uses model's default ordering
            ]

        # Admin choices
        if "admin" in form_instance.fields:
            active_admins = [
                (a.id, f"{a.user.get_full_name()}{'*' if not a.user.is_active else ''}")
                for a in Admin.objects.select_related("user").filter(
                    user__is_active=True
                )
            ]
            inactive_admins = [
                (a.id, f"{a.user.get_full_name()}*")
                for a in Admin.objects.select_related("user").filter(
                    user__is_active=False
                )
            ]
            form_instance.fields["admin"].choices = (
                [("", empty_labels.get("admin", "Select Admin..."))]
                + active_admins
                + inactive_admins
            )

        # Section choices
        if "section" in form_instance.fields:
            form_instance.fields["section"].choices = [
                ("", empty_labels.get("section", "Select Section..."))
            ] + [
                (s.id, s.name)
                for s in Section.objects.all()  # Uses model's default ordering
            ]

        # Job Type choices
        if "job_type" in form_instance.fields:
            form_instance.fields["job_type"].choices = [
                ("", empty_labels.get("job_type", "Select Job Type..."))
            ] + [
                (j.id, j.name)
                for j in JobType.objects.all()  # Uses model's default ordering
            ]

        # Contact choices
        if "contact" in form_instance.fields:
            form_instance.fields["contact"].choices = [
                ("", empty_labels.get("contact", "Select Contact..."))
            ] + [
                (c.id, c.name)
                for c in Contact.objects.all()  # Uses model's default ordering
            ]

        # Ward choices
        if "ward" in form_instance.fields:
            form_instance.fields["ward"].choices = [
                ("", empty_labels.get("ward", "Select Ward..."))
            ] + [
                (w.id, w.name)
                for w in Ward.objects.all()  # Uses model's default ordering
            ]

        # Service Type choices (from model)
        if "service_type" in form_instance.fields:
            form_instance.fields["service_type"].choices = [
                ("", empty_labels.get("service_type", "Select Service Type..."))
            ] + list(Enquiry.SERVICE_TYPE_CHOICES)

    @classmethod
    def apply_date_field_styling(
        cls,
        form_instance: forms.Form,
        field_names: List[str],
        set_defaults: bool = False,
    ) -> None:
        """
        Apply consistent styling to date fields.

        Args:
            form_instance: Django form instance
            field_names: List of date field names to style
            set_defaults: Whether to set default date values
        """
        for field_name in field_names:
            if field_name in form_instance.fields:
                field = form_instance.fields[field_name]

                # Apply Bootstrap class and date type
                field.widget.attrs.update({"class": "form-control", "type": "date"})

        # Set default dates if requested
        if set_defaults:
            today = timezone.now().date()
            three_months_ago = today - timedelta(days=90)

            if "date_from" in form_instance.fields:
                form_instance.fields["date_from"].initial = three_months_ago
            if "date_to" in form_instance.fields:
                form_instance.fields["date_to"].initial = today

    # Widget-to-type mapping for CharField subtypes
    _CHAR_WIDGET_MAP = {
        forms.Textarea: "textarea",
        forms.EmailInput: "email",
        forms.PasswordInput: "password",
    }

    # Field class to type mapping (order matters: more specific classes first)
    # DateTimeField must come before DateField since DateTimeField is a subclass
    # of DateField.
    _FIELD_TYPE_MAP = (
        ((forms.EmailField,), "email"),
        ((forms.IntegerField, forms.FloatField), "number"),
        ((forms.DateTimeField,), "datetime"),
        ((forms.DateField,), "date"),
        ((forms.ChoiceField, forms.ModelChoiceField), "select"),
        ((forms.BooleanField,), "checkbox"),
        ((forms.FileField,), "file"),
    )

    @classmethod
    def _get_char_field_type(cls, field: forms.CharField) -> str:
        """Determine the specific type for a CharField based on its widget."""
        for widget_class, field_type in cls._CHAR_WIDGET_MAP.items():
            if isinstance(field.widget, widget_class):
                return field_type
        return "text"

    @classmethod
    def _get_field_type(cls, field: forms.Field) -> str:
        """
        Determine the field type for Bootstrap class mapping.

        Args:
            field: Django form field

        Returns:
            String representing the field type
        """
        if isinstance(field, forms.CharField):
            return cls._get_char_field_type(field)

        for field_classes, field_type in cls._FIELD_TYPE_MAP:
            if isinstance(field, field_classes):
                return field_type

        return "text"  # Default fallback
