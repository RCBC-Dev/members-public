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
Comprehensive tests for application models.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from application.models import (
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
    ReferenceSequence,
)


@pytest.mark.django_db
class TestAdmin:
    """Test Admin model."""

    def test_admin_creation(self):
        user = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            first_name="Admin",
            last_name="User",
        )
        admin = Admin.objects.create(user=user)

        assert admin.user == user
        assert str(admin) == "Admin User"
        assert admin._meta.db_table == "members_app_admin"

    def test_admin_str_fallback(self):
        user = User.objects.create_user(username="admin_user")
        admin = Admin.objects.create(user=user)

        assert (
            str(admin) == ""
        )  # get_full_name returns empty string when no first/last name

    def test_admin_one_to_one_relationship(self):
        user = User.objects.create_user(username="admin_user")
        admin = Admin.objects.create(user=user)

        # Test reverse relationship
        assert user.admin == admin

        # Test cascade delete
        user.delete()
        assert not Admin.objects.filter(id=admin.id).exists()


@pytest.mark.django_db
class TestArea:
    """Test Area model."""

    def test_area_creation(self):
        area = Area.objects.create(name="Test Area", description="Test Description")

        assert area.name == "Test Area"
        assert area.description == "Test Description"
        assert str(area) == "Test Area"
        assert area._meta.db_table == "members_app_area"

    def test_area_name_unique(self):
        Area.objects.create(name="Unique Area")

        with pytest.raises(IntegrityError):
            Area.objects.create(name="Unique Area")

    def test_area_name_indexed(self):
        # Check that name field has db_index=True
        name_field = Area._meta.get_field("name")
        assert name_field.db_index is True

    def test_area_description_optional(self):
        area = Area.objects.create(name="Area Without Description")
        assert area.description == ""


@pytest.mark.django_db
class TestDepartment:
    """Test Department model."""

    def test_department_creation(self):
        department = Department.objects.create(
            name="Test Department", description="Test Description"
        )

        assert department.name == "Test Department"
        assert department.description == "Test Description"
        assert str(department) == "Test Department"
        assert department._meta.db_table == "members_app_department"

    def test_department_name_unique(self):
        Department.objects.create(name="Unique Department")

        with pytest.raises(IntegrityError):
            Department.objects.create(name="Unique Department")


@pytest.mark.django_db
class TestSection:
    """Test Section model."""

    def test_section_creation(self):
        department = Department.objects.create(name="Test Department")
        section = Section.objects.create(name="Test Section", department=department)

        assert section.name == "Test Section"
        assert section.department == department
        assert str(section) == "Test Section"
        assert section._meta.db_table == "members_app_section"

    def test_section_department_relationship(self):
        department = Department.objects.create(name="Test Department")
        section = Section.objects.create(name="Test Section", department=department)

        # Test reverse relationship
        assert section in department.sections.all()

    def test_section_department_protect_on_delete(self):
        department = Department.objects.create(name="Test Department")
        section = Section.objects.create(name="Test Section", department=department)

        # Should not be able to delete department with sections
        with pytest.raises(Exception):  # Protected foreign key
            department.delete()

    def test_section_name_unique(self):
        department = Department.objects.create(name="Test Department")
        Section.objects.create(name="Unique Section", department=department)

        with pytest.raises(IntegrityError):
            Section.objects.create(name="Unique Section", department=department)


@pytest.mark.django_db
class TestWard:
    """Test Ward model."""

    def test_ward_creation(self):
        ward = Ward.objects.create(name="Test Ward", description="Test Description")

        assert ward.name == "Test Ward"
        assert ward.description == "Test Description"
        assert str(ward) == "Test Ward"
        assert ward._meta.db_table == "members_app_ward"

    def test_ward_name_unique(self):
        Ward.objects.create(name="Unique Ward")

        with pytest.raises(IntegrityError):
            Ward.objects.create(name="Unique Ward")


@pytest.mark.django_db
class TestMember:
    """Test Member model."""

    def test_member_creation(self):
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Member",
            last_name="User",
            email="member.user@example.com",
            ward=ward,
        )

        assert member.first_name == "Member"
        assert member.last_name == "User"
        assert member.email == "member.user@example.com"
        assert member.ward == ward
        assert member.is_active is True
        assert str(member) == "Member User"
        assert member._meta.db_table == "members_app_member"

    def test_member_ward_relationship(self):
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Member",
            last_name="User",
            email="member.user@example.com",
            ward=ward,
        )

        # Test reverse relationship
        assert member in ward.members.all()

    def test_member_ward_protect_on_delete(self):
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Member",
            last_name="User",
            email="member.user@example.com",
            ward=ward,
        )

        # Should not be able to delete ward with members
        with pytest.raises(Exception):  # Protected foreign key
            ward.delete()

    def test_member_indexes(self):
        # Test that the composite index exists
        indexes = Member._meta.indexes
        ward_active_index = next(
            (idx for idx in indexes if idx.name == "member_ward_active_idx"), None
        )
        assert ward_active_index is not None
        assert ward_active_index.fields == ["ward", "is_active"]


@pytest.mark.django_db
class TestJobType:
    """Test JobType model."""

    def test_jobtype_creation(self):
        jobtype = JobType.objects.create(name="Test Job Type")

        assert jobtype.name == "Test Job Type"
        assert str(jobtype) == "Test Job Type"
        assert jobtype._meta.db_table == "members_app_jobtype"

    def test_jobtype_name_unique(self):
        JobType.objects.create(name="Unique Job Type")

        with pytest.raises(IntegrityError):
            JobType.objects.create(name="Unique Job Type")


@pytest.mark.django_db
class TestEnquiry:
    """Test Enquiry model with comprehensive scenarios."""

    def test_enquiry_creation(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        assert enquiry.title == "Test Enquiry"
        assert enquiry.description == "Test Description"
        assert enquiry.member == member
        assert enquiry.status == "open"  # New default status
        assert enquiry.created_at is not None
        assert enquiry.updated_at is not None
        assert enquiry.closed_at is None
        assert enquiry._meta.db_table == "members_app_enquiry"

    def test_enquiry_status_choices(self):
        assert Enquiry.STATUS_CHOICES == (
            ("new", "New"),
            ("open", "Open"),
            ("closed", "Closed"),
        )

    def test_enquiry_str_method(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        # Test with reference
        enquiry = Enquiry.objects.create(
            title="Test Enquiry",
            description="Test Description",
            member=member,
            reference="MEM-24-0001",
        )
        assert str(enquiry) == "MEM-24-0001 - Test Enquiry"

        # Test without reference
        enquiry_no_ref = Enquiry.objects.create(
            title="Test Enquiry No Ref", description="Test Description", member=member
        )
        assert str(enquiry_no_ref) == "No Ref - Test Enquiry No Ref"

    def test_enquiry_due_date_property(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        # Test that due_date property uses business days calculation
        # Import the utility function to calculate expected due date
        from application.utils import calculate_working_days_due_date

        expected_due_date_date = calculate_working_days_due_date(enquiry.created_at, 5)

        # Convert back to datetime with same timezone as created_at for comparison
        if expected_due_date_date:
            expected_due_date = timezone.datetime.combine(
                expected_due_date_date,
                enquiry.created_at.time(),
                tzinfo=enquiry.created_at.tzinfo,
            )
        else:
            # Fallback matches the model's fallback behavior
            expected_due_date = enquiry.created_at + timedelta(days=5)

        assert enquiry.due_date == expected_due_date

    def test_enquiry_save_auto_assignment(self):
        admin_user = User.objects.create_user(username="admin_user")
        admin = Admin.objects.create(user=admin_user)

        member_user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry(
            title="Test Enquiry", description="Test Description", member=member
        )
        enquiry._creating_user = admin_user
        enquiry.save()

        assert enquiry.admin == admin
        assert enquiry.status == "open"  # New default status

    def test_enquiry_save_closed_at_update(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        # Initially closed_at should be None
        assert enquiry.closed_at is None

        # Change status to closed
        enquiry.status = "closed"
        enquiry.save()

        assert enquiry.closed_at is not None
        assert enquiry.status == "closed"

    @override_settings(REFERENCE_TYPE="STANDARD")
    def test_enquiry_generate_reference(self):
        reference = Enquiry.generate_reference()
        current_year = timezone.now().year % 100

        assert reference.startswith(f"MEM-{current_year:02d}-")
        assert len(reference) == 11  # MEM-YY-NNNN format

    def test_enquiry_generate_reference_uniqueness(self):
        # Create some enquiries to test uniqueness
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        reference1 = Enquiry.generate_reference()
        Enquiry.objects.create(
            title="Test 1", description="Test", member=member, reference=reference1
        )

        reference2 = Enquiry.generate_reference()
        assert reference1 != reference2

    def test_enquiry_reference_unique_constraint(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        Enquiry.objects.create(
            title="Test 1", description="Test", member=member, reference="MEM-24-0001"
        )

        with pytest.raises(IntegrityError):
            Enquiry.objects.create(
                title="Test 2",
                description="Test",
                member=member,
                reference="MEM-24-0001",
            )

    def test_enquiry_relationships(self):
        # Create all related objects
        admin_user = User.objects.create_user(username="admin_user")
        admin = Admin.objects.create(user=admin_user)

        member_user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        department = Department.objects.create(name="Test Department")
        section = Section.objects.create(name="Test Section", department=department)

        area = Area.objects.create(name="Test Area")
        jobtype = JobType.objects.create(name="Test Job Type")

        contact = Contact.objects.create(
            name="Test Contact", telephone_number="123456789", section=section
        )
        contact.areas.add(area)
        contact.job_types.add(jobtype)

        enquiry = Enquiry.objects.create(
            title="Test Enquiry",
            description="Test Description",
            member=member,
            admin=admin,
            section=section,
            contact=contact,
            job_type=jobtype,
        )

        # Test all relationships
        assert enquiry.member == member
        assert enquiry.admin == admin
        assert enquiry.section == section
        assert enquiry.contact == contact
        assert enquiry.job_type == jobtype

        # Test reverse relationships
        assert enquiry in member.enquiries.all()
        assert enquiry in admin.assigned_enquiries.all()
        assert enquiry in section.enquiries.all()
        assert enquiry in contact.enquiries.all()
        assert enquiry in jobtype.enquiries.all()

    def test_enquiry_indexes(self):
        # Test that required indexes exist
        indexes = Enquiry._meta.indexes
        index_names = [idx.name for idx in indexes]

        expected_indexes = [
            "enquiry_created_desc_idx",
            "enquiry_status_created_idx",
            "enquiry_reference_idx",
            "enquiry_member_created_idx",
            "enquiry_section_created_idx",
            "enquiry_admin_created_idx",
            "enquiry_contact_created_idx",
            "enquiry_updated_desc_idx",
            "enquiry_title_idx",
            "enquiry_jobtype_created_idx",
            "enquiry_created_asc_idx",
            "enq_status_member_created_idx",
            "enq_status_section_created_idx",
        ]

        for expected_index in expected_indexes:
            assert expected_index in index_names


@pytest.mark.django_db
class TestEnquiryHistory:
    """Test EnquiryHistory model."""

    def test_enquiry_history_creation(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        history = EnquiryHistory.objects.create(
            enquiry=enquiry, note="Test note", created_by=user
        )

        assert history.enquiry == enquiry
        assert history.note == "Test note"
        assert history.created_by == user
        assert history.created_at is not None
        assert history._meta.db_table == "members_app_enquiryhistory"

    def test_enquiry_history_str_method(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        history = EnquiryHistory.objects.create(
            enquiry=enquiry, note="Test note", created_by=user
        )

        assert str(history) == f"History for Test Enquiry at {history.created_at}"

    def test_enquiry_history_save_updates_enquiry(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry",
            description="Test Description",
            member=member,
            status="new",  # Manually set to 'new' to test the status change logic
        )

        original_updated_at = enquiry.updated_at
        original_status = enquiry.status

        # Add a small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        # Create history entry
        history = EnquiryHistory.objects.create(
            enquiry=enquiry, note="Test note", created_by=user
        )

        # Refresh enquiry from database
        enquiry.refresh_from_db()

        # Check that updated_at was changed (or at least not less than original)
        assert enquiry.updated_at >= original_updated_at

        # Check that status changed from 'new' to 'open'
        assert original_status == "new"
        assert enquiry.status == "open"

    def test_enquiry_history_relationship(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        history = EnquiryHistory.objects.create(
            enquiry=enquiry, note="Test note", created_by=user
        )

        # Test reverse relationship
        assert history in enquiry.history.all()

    def test_enquiry_history_indexes(self):
        indexes = EnquiryHistory._meta.indexes
        index_names = [idx.name for idx in indexes]

        assert "history_enquiry_created_idx" in index_names


@pytest.mark.django_db
class TestContact:
    """Test Contact model."""

    def test_contact_creation(self):
        department = Department.objects.create(name="Test Department")
        section = Section.objects.create(name="Test Section", department=department)
        area = Area.objects.create(name="Test Area")
        jobtype = JobType.objects.create(name="Test Job Type")

        contact = Contact.objects.create(
            name="Test Contact",
            description="Test Description",
            telephone_number="123456789",
            section=section,
        )
        contact.areas.add(area)
        contact.job_types.add(jobtype)

        assert contact.name == "Test Contact"
        assert contact.description == "Test Description"
        assert contact.telephone_number == "123456789"
        assert contact.section == section
        assert area in contact.areas.all()
        assert jobtype in contact.job_types.all()
        assert str(contact) == "Test Contact"
        assert contact._meta.db_table == "members_app_contact"

    def test_contact_name_unique(self):
        department = Department.objects.create(name="Test Department")
        section = Section.objects.create(name="Test Section", department=department)

        Contact.objects.create(
            name="Unique Contact", telephone_number="123456789", section=section
        )

        with pytest.raises(IntegrityError):
            Contact.objects.create(
                name="Unique Contact", telephone_number="987654321", section=section
            )

    def test_contact_relationships(self):
        department = Department.objects.create(name="Test Department")
        section = Section.objects.create(name="Test Section", department=department)
        area = Area.objects.create(name="Test Area")
        jobtype = JobType.objects.create(name="Test Job Type")

        contact = Contact.objects.create(
            name="Test Contact", telephone_number="123456789", section=section
        )
        contact.areas.add(area)
        contact.job_types.add(jobtype)

        # Test reverse relationships
        assert contact in section.contacts.all()
        assert contact in area.contacts.all()
        assert contact in jobtype.contacts.all()


@pytest.mark.django_db
class TestReferenceSequence:
    """Test ReferenceSequence model and reference generation (STANDARD mode)."""

    @pytest.fixture(autouse=True)
    def force_standard_mode(self, settings):
        settings.REFERENCE_TYPE = "STANDARD"

    def test_reference_sequence_creation(self):
        sequence = ReferenceSequence.objects.create(year=25, next_number=1)
        assert sequence.year == 25
        assert sequence.next_number == 1
        assert str(sequence) == "Year 25: Next #1"

    def test_get_next_reference_new_year(self):
        """Test reference generation for a new year."""
        # Clear any existing sequences
        ReferenceSequence.objects.all().delete()

        reference = ReferenceSequence.get_next_reference()

        # Should create MEM-YY-0001 format
        current_year = timezone.now().year % 100
        expected = f"MEM-{current_year:02d}-0001"
        assert reference == expected

        # Check sequence was created
        sequence = ReferenceSequence.objects.get(year=current_year)
        assert sequence.next_number == 2  # Ready for next reference

    def test_get_next_reference_existing_year(self):
        """Test reference generation for existing year."""
        current_year = timezone.now().year % 100

        # Create existing sequence
        ReferenceSequence.objects.create(year=current_year, next_number=5)

        reference = ReferenceSequence.get_next_reference()
        expected = f"MEM-{current_year:02d}-0005"
        assert reference == expected

        # Check sequence was incremented
        sequence = ReferenceSequence.objects.get(year=current_year)
        assert sequence.next_number == 6

    def test_reference_generation_sequential(self):
        """Test that sequential reference generation works correctly."""
        current_year = timezone.now().year % 100
        ReferenceSequence.objects.all().delete()

        references = []

        # Generate 5 references sequentially
        for _ in range(5):
            ref = ReferenceSequence.get_next_reference()
            references.append(ref)

        # All references should be unique and sequential
        assert len(references) == 5
        assert len(set(references)) == 5  # All unique

        expected_refs = [f"MEM-{current_year:02d}-{i:04d}" for i in range(1, 6)]
        assert references == expected_refs

    def test_reference_generation_with_existing_enquiry(self):
        """Test that reference generation skips existing references."""
        current_year = timezone.now().year % 100

        # Create user and member for enquiry
        user = User.objects.create_user(username="test_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        # Create an enquiry with a specific reference
        existing_ref = f"MEM-{current_year:02d}-0001"
        Enquiry.objects.create(
            title="Existing Enquiry",
            description="Test",
            member=member,
            reference=existing_ref,
        )

        # Set sequence to generate the same number
        ReferenceSequence.objects.create(year=current_year, next_number=1)

        # Should skip the existing reference
        new_reference = ReferenceSequence.get_next_reference()
        expected = f"MEM-{current_year:02d}-0002"
        assert new_reference == expected


@pytest.mark.django_db
class TestReferenceSequenceFinancial:
    """Test financial year reference generation (REFERENCE_TYPE=FINANCIAL)."""

    def _make_aware(self, year, month, day):
        """Helper to create a timezone-aware datetime."""
        return timezone.make_aware(datetime(year, month, day))

    def test_financial_year_key_april(self):
        """April is the start of a new financial year."""
        now = self._make_aware(2026, 4, 1)
        key, label = ReferenceSequence._get_financial_year_key_and_label(now)
        assert key == 2627
        assert label == "26/27"

    def test_financial_year_key_march(self):
        """March still belongs to the previous financial year."""
        now = self._make_aware(2026, 3, 31)
        key, label = ReferenceSequence._get_financial_year_key_and_label(now)
        assert key == 2526
        assert label == "25/26"

    def test_financial_year_key_january(self):
        """January belongs to the financial year that started the previous April."""
        now = self._make_aware(2026, 1, 15)
        key, label = ReferenceSequence._get_financial_year_key_and_label(now)
        assert key == 2526
        assert label == "25/26"

    def test_get_next_reference_financial_format(self):
        """Financial mode produces MEM-YY/YY-NNNN references."""
        ReferenceSequence.objects.all().delete()
        april_2026 = self._make_aware(2026, 4, 1)

        with self.settings_override("FINANCIAL"):
            with patch("application.models.timezone.now", return_value=april_2026):
                reference = ReferenceSequence.get_next_reference()

        assert reference == "MEM-26/27-0001"

    def test_financial_sequence_resets_on_new_financial_year(self):
        """Sequence resets to 0001 when financial year changes."""
        ReferenceSequence.objects.all().delete()
        march_2026 = self._make_aware(2026, 3, 31)
        april_2026 = self._make_aware(2026, 4, 1)

        with self.settings_override("FINANCIAL"):
            with patch("application.models.timezone.now", return_value=march_2026):
                ref_march = ReferenceSequence.get_next_reference()

            with patch("application.models.timezone.now", return_value=april_2026):
                ref_april = ReferenceSequence.get_next_reference()

        assert ref_march == "MEM-25/26-0001"
        assert ref_april == "MEM-26/27-0001"

    def test_financial_sequence_continues_within_year(self):
        """Sequence increments within the same financial year."""
        ReferenceSequence.objects.all().delete()
        # Pre-seed a sequence for FY 26/27 (key=2627)
        ReferenceSequence.objects.create(year=2627, next_number=5)
        april_2026 = self._make_aware(2026, 4, 15)

        with self.settings_override("FINANCIAL"):
            with patch("application.models.timezone.now", return_value=april_2026):
                reference = ReferenceSequence.get_next_reference()

        assert reference == "MEM-26/27-0005"
        assert ReferenceSequence.objects.get(year=2627).next_number == 6

    def test_financial_and_standard_sequences_do_not_collide(self):
        """STANDARD (year=26) and FINANCIAL (year=2627) keys never clash."""
        ReferenceSequence.objects.all().delete()
        april_2026 = self._make_aware(2026, 4, 1)

        with self.settings_override("STANDARD"):
            with patch("application.models.timezone.now", return_value=april_2026):
                std_ref = ReferenceSequence.get_next_reference()

        with self.settings_override("FINANCIAL"):
            with patch("application.models.timezone.now", return_value=april_2026):
                fin_ref = ReferenceSequence.get_next_reference()

        assert std_ref == "MEM-26-0001"
        assert fin_ref == "MEM-26/27-0001"
        assert ReferenceSequence.objects.count() == 2

    @staticmethod
    def settings_override(reference_type):
        """Context manager to temporarily override REFERENCE_TYPE."""
        return override_settings(REFERENCE_TYPE=reference_type)


@pytest.mark.django_db
class TestReferenceSequenceModeSwitch:
    """
    Test behaviour when switching between STANDARD and FINANCIAL modes.

    Each test date exercises a different relationship between the two modes:
      Jan 1  - STANDARD year 26,  FINANCIAL year 25/26  (different periods, different keys)
      Apr 1  - STANDARD year 26,  FINANCIAL year 26/27  (same calendar year, different periods)
      Oct 15 - STANDARD year 26,  FINANCIAL year 26/27  (mid-year, both well within their period)
      Mar 31 - STANDARD year 27,  FINANCIAL year 26/27  (STANDARD has rolled but FINANCIAL has not)

    Key assertion in all cases: switching mode never corrupts either counter and
    sequences from the two modes are stored under different keys so they never collide.
    """

    @staticmethod
    def _make_aware(year, month, day):
        return timezone.make_aware(datetime(year, month, day))

    @staticmethod
    def _override(reference_type):
        return override_settings(REFERENCE_TYPE=reference_type)

    # ------------------------------------------------------------------
    # Helpers to generate N references under a given mode/date
    # ------------------------------------------------------------------
    def _gen(self, mode, dt, count=1):
        refs = []
        with self._override(mode):
            with patch("application.models.timezone.now", return_value=dt):
                for _ in range(count):
                    refs.append(ReferenceSequence.get_next_reference())
        return refs if count > 1 else refs[0]

    # ------------------------------------------------------------------
    # January 1 - STANDARD rolls to new calendar year but FINANCIAL
    # is still in the old financial year (25/26).
    # ------------------------------------------------------------------
    def test_standard_to_financial_jan1(self):
        """Switch from STANDARD to FINANCIAL on 1 Jan 2026."""
        ReferenceSequence.objects.all().delete()
        jan1 = self._make_aware(2026, 1, 1)

        std_ref = self._gen("STANDARD", jan1)        # MEM-26-0001, key=26
        fin_ref = self._gen("FINANCIAL", jan1)       # MEM-25/26-0001, key=2526

        assert std_ref == "MEM-26-0001"
        assert fin_ref == "MEM-25/26-0001"
        assert ReferenceSequence.objects.get(year=26).next_number == 2
        assert ReferenceSequence.objects.get(year=2526).next_number == 2

    def test_financial_to_standard_jan1(self):
        """Switch from FINANCIAL to STANDARD on 1 Jan 2026."""
        ReferenceSequence.objects.all().delete()
        jan1 = self._make_aware(2026, 1, 1)

        fin_ref = self._gen("FINANCIAL", jan1)       # MEM-25/26-0001, key=2526
        std_ref = self._gen("STANDARD", jan1)        # MEM-26-0001, key=26

        assert fin_ref == "MEM-25/26-0001"
        assert std_ref == "MEM-26-0001"
        assert ReferenceSequence.objects.count() == 2

    # ------------------------------------------------------------------
    # April 1 - financial year rolls over; STANDARD is still year 26.
    # ------------------------------------------------------------------
    def test_standard_to_financial_apr1(self):
        """Switch from STANDARD to FINANCIAL on 1 Apr 2026."""
        ReferenceSequence.objects.all().delete()
        apr1 = self._make_aware(2026, 4, 1)

        std_ref = self._gen("STANDARD", apr1)        # MEM-26-0001, key=26
        fin_ref = self._gen("FINANCIAL", apr1)       # MEM-26/27-0001, key=2627

        assert std_ref == "MEM-26-0001"
        assert fin_ref == "MEM-26/27-0001"
        assert ReferenceSequence.objects.count() == 2

    def test_financial_to_standard_apr1(self):
        """Switch from FINANCIAL to STANDARD on 1 Apr 2026."""
        ReferenceSequence.objects.all().delete()
        apr1 = self._make_aware(2026, 4, 1)

        fin_ref = self._gen("FINANCIAL", apr1)       # MEM-26/27-0001, key=2627
        std_ref = self._gen("STANDARD", apr1)        # MEM-26-0001, key=26

        assert fin_ref == "MEM-26/27-0001"
        assert std_ref == "MEM-26-0001"
        assert ReferenceSequence.objects.count() == 2

    # ------------------------------------------------------------------
    # October 15 - mid-year, both modes well within their period.
    # ------------------------------------------------------------------
    def test_standard_to_financial_oct15(self):
        """Switch from STANDARD to FINANCIAL on 15 Oct 2026."""
        ReferenceSequence.objects.all().delete()
        oct15 = self._make_aware(2026, 10, 15)

        std_refs = self._gen("STANDARD", oct15, count=3)   # MEM-26-0001..0003
        fin_ref  = self._gen("FINANCIAL", oct15)            # MEM-26/27-0001

        assert std_refs == ["MEM-26-0001", "MEM-26-0002", "MEM-26-0003"]
        assert fin_ref == "MEM-26/27-0001"
        assert ReferenceSequence.objects.get(year=26).next_number == 4
        assert ReferenceSequence.objects.get(year=2627).next_number == 2

    def test_financial_to_standard_oct15(self):
        """Switch from FINANCIAL to STANDARD on 15 Oct 2026."""
        ReferenceSequence.objects.all().delete()
        oct15 = self._make_aware(2026, 10, 15)

        fin_refs = self._gen("FINANCIAL", oct15, count=3)  # MEM-26/27-0001..0003
        std_ref  = self._gen("STANDARD", oct15)             # MEM-26-0001

        assert fin_refs == ["MEM-26/27-0001", "MEM-26/27-0002", "MEM-26/27-0003"]
        assert std_ref == "MEM-26-0001"

    # ------------------------------------------------------------------
    # March 31 - last day of financial year but STANDARD has already
    # rolled to year 27 (1 Jan 2027).
    # ------------------------------------------------------------------
    def test_standard_to_financial_mar31(self):
        """Switch from STANDARD to FINANCIAL on 31 Mar 2027."""
        ReferenceSequence.objects.all().delete()
        mar31 = self._make_aware(2027, 3, 31)

        std_ref = self._gen("STANDARD", mar31)       # MEM-27-0001, key=27
        fin_ref = self._gen("FINANCIAL", mar31)      # MEM-26/27-0001, key=2627

        assert std_ref == "MEM-27-0001"
        assert fin_ref == "MEM-26/27-0001"
        assert ReferenceSequence.objects.count() == 2

    def test_financial_to_standard_mar31(self):
        """Switch from FINANCIAL to STANDARD on 31 Mar 2027."""
        ReferenceSequence.objects.all().delete()
        mar31 = self._make_aware(2027, 3, 31)

        fin_ref = self._gen("FINANCIAL", mar31)      # MEM-26/27-0001, key=2627
        std_ref = self._gen("STANDARD", mar31)       # MEM-27-0001, key=27

        assert fin_ref == "MEM-26/27-0001"
        assert std_ref == "MEM-27-0001"
        assert ReferenceSequence.objects.count() == 2

    # ------------------------------------------------------------------
    # Switching back: counter resumes from where it left off.
    # ------------------------------------------------------------------
    def test_switching_back_resumes_counter(self):
        """Switching back to a mode resumes its counter, not starting from 1."""
        ReferenceSequence.objects.all().delete()
        oct15 = self._make_aware(2026, 10, 15)

        # Start in STANDARD - generates 0001, 0002, 0003
        self._gen("STANDARD", oct15, count=3)

        # Switch to FINANCIAL - independent counter starts at 0001
        fin_ref = self._gen("FINANCIAL", oct15)
        assert fin_ref == "MEM-26/27-0001"

        # Switch back to STANDARD - should resume at 0004
        std_ref = self._gen("STANDARD", oct15)
        assert std_ref == "MEM-26-0004"


@pytest.mark.django_db
class TestEnquiryAttachment:
    """Test EnquiryAttachment model."""

    def test_enquiry_attachment_creation(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename="test.jpg",
            file_path="attachments/test.jpg",
            file_size=1024,
            uploaded_by=user,
        )

        assert attachment.enquiry == enquiry
        assert attachment.filename == "test.jpg"
        assert attachment.file_path == "attachments/test.jpg"
        assert attachment.file_size == 1024
        assert attachment.uploaded_by == user
        assert attachment.uploaded_at is not None
        assert attachment._meta.db_table == "members_app_enquiryattachment"

    def test_enquiry_attachment_str_method(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry",
            description="Test Description",
            member=member,
            reference="MEM-24-0001",
        )

        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename="test.jpg",
            file_path="attachments/test.jpg",
            file_size=1024,
            uploaded_by=user,
        )

        assert str(attachment) == "test.jpg - MEM-24-0001"

    def test_enquiry_attachment_file_url_property(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename="test.jpg",
            file_path="attachments/test.jpg",
            file_size=1024,
            uploaded_by=user,
        )

        # Mock settings.MEDIA_URL for the test
        from unittest.mock import patch

        with patch("django.conf.settings.MEDIA_URL", "/media/"):
            assert attachment.file_url == "/media/attachments/test.jpg"

    def test_enquiry_attachment_relationship(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename="test.jpg",
            file_path="attachments/test.jpg",
            file_size=1024,
            uploaded_by=user,
        )

        # Test reverse relationship
        assert attachment in enquiry.attachments.all()

    def test_enquiry_attachment_cascade_delete(self):
        user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename="test.jpg",
            file_path="attachments/test.jpg",
            file_size=1024,
            uploaded_by=user,
        )

        attachment_id = attachment.id

        # Delete enquiry should cascade to attachment
        enquiry.delete()

        assert not EnquiryAttachment.objects.filter(id=attachment_id).exists()

    def test_enquiry_attachment_indexes(self):
        indexes = EnquiryAttachment._meta.indexes
        index_names = [idx.name for idx in indexes]

        assert "attachment_idx" in index_names


@pytest.mark.django_db
class TestAudit:
    """Test Audit model."""

    def test_audit_creation(self):
        user = User.objects.create_user(username="test_user")
        member_user = User.objects.create_user(username="member_user")
        ward = Ward.objects.create(name="Test Ward")
        member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email=f"test.member{uuid.uuid4().hex[:8]}@example.com",
            ward=ward,
        )

        enquiry = Enquiry.objects.create(
            title="Test Enquiry", description="Test Description", member=member
        )

        audit = Audit.objects.create(
            user=user,
            enquiry=enquiry,
            action_details="Test action",
            ip_address="127.0.0.1",
        )

        assert audit.user == user
        assert audit.enquiry == enquiry
        assert audit.action_details == "Test action"
        assert audit.ip_address == "127.0.0.1"
        assert audit.action_datetime is not None
        assert audit._meta.db_table == "members_app_audit"

    def test_audit_nullable_fields(self):
        # Test that user and enquiry can be null
        audit = Audit.objects.create(action_details="Test action without user/enquiry")

        assert audit.user is None
        assert audit.enquiry is None
        assert audit.action_details == "Test action without user/enquiry"
