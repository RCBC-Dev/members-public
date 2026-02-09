from datetime import timedelta
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinLengthValidator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, HTML
from tinymce.widgets import TinyMCE

from .models import (
    Enquiry,
    EnquiryHistory,
    Member,
    Admin,
    Section,
    Contact,
    JobType,
    Ward,
)
from .form_styling_service import FormStyleService


class BaseFormHelper(FormHelper):
    """Base helper for styling forms consistently with crispy forms."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = "post"
        self.form_class = "needs-validation"
        self.attrs = {"novalidate": ""}
        self.label_class = "form-label"
        self.field_class = "mb-3"
        self.help_text_inline = True
        self.error_text_inline = True
        self.form_show_errors = True


class EnquiryForm(forms.ModelForm):
    """Form for creating and editing enquiries."""

    class Meta:
        model = Enquiry
        fields = ["title", "description", "member", "section", "contact", "job_type"]
        widgets = {
            "description": TinyMCE(
                attrs={
                    "cols": 80,
                    "rows": 30,
                    "class": "form-control",
                    "placeholder": "Enter enquiry description...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = BaseFormHelper()
        self.helper.form_id = "enquiry-form"

        # Set default querysets to filter for active members (other models use default ordering from Meta)
        self.fields["member"].queryset = Member.objects.filter(is_active=True)

        # Define the form layout with crispy forms
        self.helper.layout = Layout(
            Row(Column("title", css_class="col-12")),
            Row(Column("description", css_class="col-12")),
            Row(
                Column("member", css_class="col-md-6"),
                Column("section", css_class="col-md-6"),
            ),
            Row(
                Column("contact", css_class="col-md-6"),
                Column("job_type", css_class="col-md-6"),
            ),
            Row(
                Column(
                    Submit("submit", "Save Enquiry", css_class="btn btn-primary"),
                    css_class="col-12 text-end",
                )
            ),
        )

        # Apply unified form styling
        FormStyleService.apply_text_field_styling(
            self, {"title": {"placeholder": "Brief title for the enquiry"}}
        )

        # Apply select field styling
        FormStyleService.apply_select_field_styling(
            self, ["member", "section", "contact", "job_type"]
        )

        # Make contact and job_type required
        self.fields["contact"].required = True
        self.fields["job_type"].required = True


class StaffEnquiryForm(EnquiryForm):
    """Form for staff to create and edit enquiries. Admin assignment and status are handled automatically."""

    class Meta(EnquiryForm.Meta):
        # Remove admin and status fields - these are now handled automatically
        fields = EnquiryForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_id = "staff-enquiry-form"

        # No additional fields to add - admin and status are automatic


class EnquiryHistoryForm(forms.ModelForm):
    """Form for adding history/comments to enquiries."""

    # User-selectable note types (including email types for manual selection)
    USER_NOTE_TYPE_CHOICES = [
        ("general", "General Note"),
        ("emailed_member", "Emailed Member"),
        ("emailed_contact", "Emailed Contact"),
        ("phoned_contact", "Phoned Contact"),
        ("chased_contact", "Chased Contact"),
        ("email_incoming", "Incoming Email"),
        ("email_outgoing", "Outgoing Email"),
    ]

    note_type = forms.ChoiceField(
        choices=USER_NOTE_TYPE_CHOICES,
        initial="general",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 12}),
        validators=[
            MinLengthValidator(10, message="Note must be at least 10 characters long.")
        ],
        help_text="Minimum 10 characters required.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = BaseFormHelper()
        self.helper.form_id = "enquiry-history-form"
        self.helper.layout = Layout(
            Row(
                Column("note_type", css_class="col-md-2"),
                Column(
                    HTML(
                        """
                    <!-- Email Update Dropzone (Visible) -->
                    <div class="mb-3">
                        <label class="form-label small text-muted">Quick Email Import:</label>
                        <!-- Email Dropzone -->
                        <div id="email-update-dropzone" class="email-dropzone-visible border-3 border-dashed border-info rounded p-4 text-center bg-light">
                            <div class="dropzone-content">
                                <i class="bi bi-cloud-upload fs-2 text-info mb-2 d-block"></i>
                                <div class="fw-bold text-info mb-1">Drop Email Files Here</div>
                                <div class="small text-muted">Drag and drop Outlook messages (.msg, .eml)</div>
                                <div class="small text-muted mt-1">
                                    <i class="bi bi-info-circle me-1"></i>Content will auto-populate the note below
                                </div>
                            </div>
                            <div class="dropzone-loading d-none">
                                <div class="spinner-border text-info mb-2" role="status">
                                    <span class="visually-hidden">Processing...</span>
                                </div>
                                <div class="fw-bold text-info">Processing email...</div>
                                <div class="small text-muted">Please wait</div>
                            </div>
                        </div>


                    </div>
                    """
                    ),
                    css_class="col-md-10",
                ),
            ),
            Row(Column("note", css_class="col-12")),
            Row(
                Column(
                    HTML(
                        """
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex gap-2">
                            <!-- Email buttons will be inserted here by template -->
                            <div id="email-buttons-placeholder"></div>
                        </div>
                        <div>
                            <button type="submit" class="btn btn-primary">Add Note</button>
                        </div>
                    </div>
                    """
                    ),
                    css_class="col-12",
                )
            ),
        )

        # Apply unified form styling
        FormStyleService.apply_text_field_styling(
            self,
            {
                "note": {
                    "rows": 12,
                    "placeholder": "Add your note or comment about this enquiry...",
                }
            },
        )

    class Meta:
        model = EnquiryHistory
        fields = ["note_type", "note"]
        labels = {
            "note_type": "Note Type",
            "note": "Note/Comment",
        }


class EnquiryFilterForm(forms.Form):
    """Form for filtering enquiries in the list view."""

    # Simplified status choices for UI - 'new' is treated as 'open' in workflow
    STATUS_CHOICES = [
        ("", "All Enquiries"),
        ("open", "Open"),  # This will include both 'new' and 'open' in the backend
        ("closed", "Closed"),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        initial="",  # Default to All Enquiries
    )

    member = forms.ChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
    )

    admin = forms.ChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
    )

    section = forms.ChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
    )

    job_type = forms.ChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
    )

    service_type = forms.ChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
    )

    contact = forms.ChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
    )

    ward = forms.ChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
    )

    overdue_only = forms.BooleanField(
        required=False, label="Show overdue enquiries only"
    )

    date_from = forms.DateField(
        required=False,
        label="From Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    date_to = forms.DateField(
        required=False,
        label="To Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    # Date range quick select
    DATE_RANGE_CHOICES = [
        ("all", "All time"),
        ("3months", "Last 3 months"),
        ("6months", "Last 6 months"),
        ("12months", "Last 12 months"),
        ("custom", "Custom Range"),
    ]

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        required=False,
        initial="12months",  # Default to Last 12 months when no dates provided
        label="Date Range",
    )

    search = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply unified form styling
        FormStyleService.apply_bootstrap_styling(self)

        # Apply select field styling with filter labels
        FormStyleService.apply_select_field_styling(
            self,
            ["status", "member", "admin", "section", "job_type", "service_type", "contact", "ward"],
            use_filter_labels=True,
        )

        # Apply date field styling with defaults
        FormStyleService.apply_date_field_styling(
            self, ["date_from", "date_to"], set_defaults=True
        )

        # Apply text field styling
        FormStyleService.apply_text_field_styling(
            self,
            {
                "search": {
                    "placeholder": "Search reference, title, or description (powerful search)...",
                    "maxlength": 100,
                }
            },
        )

        # Set special attributes for date_range field
        self.fields["date_range"].widget.attrs["id"] = "id_date_range"

        # Populate choice fields using centralized service
        FormStyleService.populate_choice_fields(self, use_filter_labels=True)
