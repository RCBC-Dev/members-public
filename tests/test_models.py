"""
Comprehensive tests for application models.
"""

import pytest
import uuid
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta

from application.models import (
    Admin, Area, Department, Section, Ward, Member, JobType,
    Enquiry, EnquiryHistory, Audit, Contact, EnquiryAttachment, ReferenceSequence
)


@pytest.mark.django_db
class TestAdmin:
    """Test Admin model."""
    
    def test_admin_creation(self):
        user = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            first_name='Admin',
            last_name='User'
        )
        admin = Admin.objects.create(user=user)
        
        assert admin.user == user
        assert str(admin) == 'Admin User'
        assert admin._meta.db_table == 'members_app_admin'
    
    def test_admin_str_fallback(self):
        user = User.objects.create_user(username='admin_user')
        admin = Admin.objects.create(user=user)
        
        assert str(admin) == ''  # get_full_name returns empty string when no first/last name
    
    def test_admin_one_to_one_relationship(self):
        user = User.objects.create_user(username='admin_user')
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
        area = Area.objects.create(
            name='Test Area',
            description='Test Description'
        )
        
        assert area.name == 'Test Area'
        assert area.description == 'Test Description'
        assert str(area) == 'Test Area'
        assert area._meta.db_table == 'members_app_area'
    
    def test_area_name_unique(self):
        Area.objects.create(name='Unique Area')
        
        with pytest.raises(IntegrityError):
            Area.objects.create(name='Unique Area')
    
    def test_area_name_indexed(self):
        # Check that name field has db_index=True
        name_field = Area._meta.get_field('name')
        assert name_field.db_index is True
    
    def test_area_description_optional(self):
        area = Area.objects.create(name='Area Without Description')
        assert area.description == ''


@pytest.mark.django_db
class TestDepartment:
    """Test Department model."""
    
    def test_department_creation(self):
        department = Department.objects.create(
            name='Test Department',
            description='Test Description'
        )
        
        assert department.name == 'Test Department'
        assert department.description == 'Test Description'
        assert str(department) == 'Test Department'
        assert department._meta.db_table == 'members_app_department'
    
    def test_department_name_unique(self):
        Department.objects.create(name='Unique Department')
        
        with pytest.raises(IntegrityError):
            Department.objects.create(name='Unique Department')


@pytest.mark.django_db
class TestSection:
    """Test Section model."""
    
    def test_section_creation(self):
        department = Department.objects.create(name='Test Department')
        section = Section.objects.create(
            name='Test Section',
            department=department
        )
        
        assert section.name == 'Test Section'
        assert section.department == department
        assert str(section) == 'Test Section'
        assert section._meta.db_table == 'members_app_section'
    
    def test_section_department_relationship(self):
        department = Department.objects.create(name='Test Department')
        section = Section.objects.create(name='Test Section', department=department)
        
        # Test reverse relationship
        assert section in department.sections.all()
    
    def test_section_department_protect_on_delete(self):
        department = Department.objects.create(name='Test Department')
        section = Section.objects.create(name='Test Section', department=department)
        
        # Should not be able to delete department with sections
        with pytest.raises(Exception):  # Protected foreign key
            department.delete()
    
    def test_section_name_unique(self):
        department = Department.objects.create(name='Test Department')
        Section.objects.create(name='Unique Section', department=department)
        
        with pytest.raises(IntegrityError):
            Section.objects.create(name='Unique Section', department=department)


@pytest.mark.django_db
class TestWard:
    """Test Ward model."""
    
    def test_ward_creation(self):
        ward = Ward.objects.create(
            name='Test Ward',
            description='Test Description'
        )
        
        assert ward.name == 'Test Ward'
        assert ward.description == 'Test Description'
        assert str(ward) == 'Test Ward'
        assert ward._meta.db_table == 'members_app_ward'
    
    def test_ward_name_unique(self):
        Ward.objects.create(name='Unique Ward')
        
        with pytest.raises(IntegrityError):
            Ward.objects.create(name='Unique Ward')


@pytest.mark.django_db
class TestMember:
    """Test Member model."""
    
    def test_member_creation(self):
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Member',
            last_name='User',
            email='member.user@example.com',
            ward=ward
        )
        
        assert member.first_name == 'Member'
        assert member.last_name == 'User'
        assert member.email == 'member.user@example.com'
        assert member.ward == ward
        assert member.is_active is True
        assert str(member) == 'Member User'
        assert member._meta.db_table == 'members_app_member'
    
    def test_member_ward_relationship(self):
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Member',
            last_name='User', 
            email='member.user@example.com',
            ward=ward
        )
        
        # Test reverse relationship
        assert member in ward.members.all()
    
    def test_member_ward_protect_on_delete(self):
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Member',
            last_name='User',
            email='member.user@example.com', 
            ward=ward
        )
        
        # Should not be able to delete ward with members
        with pytest.raises(Exception):  # Protected foreign key
            ward.delete()
    
    def test_member_indexes(self):
        # Test that the composite index exists
        indexes = Member._meta.indexes
        ward_active_index = next(
            (idx for idx in indexes if idx.name == 'member_ward_active_idx'),
            None
        )
        assert ward_active_index is not None
        assert ward_active_index.fields == ['ward', 'is_active']


@pytest.mark.django_db
class TestJobType:
    """Test JobType model."""
    
    def test_jobtype_creation(self):
        jobtype = JobType.objects.create(name='Test Job Type')
        
        assert jobtype.name == 'Test Job Type'
        assert str(jobtype) == 'Test Job Type'
        assert jobtype._meta.db_table == 'members_app_jobtype'
    
    def test_jobtype_name_unique(self):
        JobType.objects.create(name='Unique Job Type')
        
        with pytest.raises(IntegrityError):
            JobType.objects.create(name='Unique Job Type')


@pytest.mark.django_db
class TestEnquiry:
    """Test Enquiry model with comprehensive scenarios."""
    
    def test_enquiry_creation(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        assert enquiry.title == 'Test Enquiry'
        assert enquiry.description == 'Test Description'
        assert enquiry.member == member
        assert enquiry.status == 'open'  # New default status
        assert enquiry.created_at is not None
        assert enquiry.updated_at is not None
        assert enquiry.closed_at is None
        assert enquiry._meta.db_table == 'members_app_enquiry'
    
    def test_enquiry_status_choices(self):
        assert Enquiry.STATUS_CHOICES == (
            ('new', 'New'),
            ('open', 'Open'),
            ('closed', 'Closed'),
        )
    
    def test_enquiry_str_method(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        # Test with reference
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member,
            reference='MEM-24-0001'
        )
        assert str(enquiry) == 'MEM-24-0001 - Test Enquiry'
        
        # Test without reference
        enquiry_no_ref = Enquiry.objects.create(
            title='Test Enquiry No Ref',
            description='Test Description',
            member=member
        )
        assert str(enquiry_no_ref) == 'No Ref - Test Enquiry No Ref'
    
    def test_enquiry_due_date_property(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
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
                tzinfo=enquiry.created_at.tzinfo
            )
        else:
            # Fallback matches the model's fallback behavior
            expected_due_date = enquiry.created_at + timedelta(days=5)
        
        assert enquiry.due_date == expected_due_date
    
    def test_enquiry_save_auto_assignment(self):
        admin_user = User.objects.create_user(username='admin_user')
        admin = Admin.objects.create(user=admin_user)
        
        member_user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        enquiry._creating_user = admin_user
        enquiry.save()
        
        assert enquiry.admin == admin
        assert enquiry.status == 'open'  # New default status
    
    def test_enquiry_save_closed_at_update(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        # Initially closed_at should be None
        assert enquiry.closed_at is None
        
        # Change status to closed
        enquiry.status = 'closed'
        enquiry.save()
        
        assert enquiry.closed_at is not None
        assert enquiry.status == 'closed'
    
    def test_enquiry_generate_reference(self):
        reference = Enquiry.generate_reference()
        current_year = timezone.now().year % 100
        
        assert reference.startswith(f'MEM-{current_year:02d}-')
        assert len(reference) == 11  # MEM-YY-NNNN format
    
    def test_enquiry_generate_reference_uniqueness(self):
        # Create some enquiries to test uniqueness
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        reference1 = Enquiry.generate_reference()
        Enquiry.objects.create(
            title='Test 1',
            description='Test',
            member=member,
            reference=reference1
        )
        
        reference2 = Enquiry.generate_reference()
        assert reference1 != reference2
    
    def test_enquiry_reference_unique_constraint(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        Enquiry.objects.create(
            title='Test 1',
            description='Test',
            member=member,
            reference='MEM-24-0001'
        )
        
        with pytest.raises(IntegrityError):
            Enquiry.objects.create(
                title='Test 2',
                description='Test',
                member=member,
                reference='MEM-24-0001'
            )
    
    def test_enquiry_relationships(self):
        # Create all related objects
        admin_user = User.objects.create_user(username='admin_user')
        admin = Admin.objects.create(user=admin_user)
        
        member_user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        department = Department.objects.create(name='Test Department')
        section = Section.objects.create(name='Test Section', department=department)
        
        area = Area.objects.create(name='Test Area')
        jobtype = JobType.objects.create(name='Test Job Type')
        
        contact = Contact.objects.create(
            name='Test Contact',
            telephone_number='123456789',
            section=section
        )
        contact.areas.add(area)
        contact.job_types.add(jobtype)
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member,
            admin=admin,
            section=section,
            contact=contact,
            job_type=jobtype
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
            'enquiry_created_desc_idx',
            'enquiry_status_created_idx',
            'enquiry_reference_idx',
            'enquiry_member_created_idx',
            'enquiry_section_created_idx',
            'enquiry_admin_created_idx',
            'enquiry_contact_created_idx',
            'enquiry_updated_desc_idx',
            'enquiry_title_idx',
            'enquiry_jobtype_created_idx',
            'enquiry_created_asc_idx',
            'enq_status_member_created_idx',
            'enq_status_section_created_idx',
        ]
        
        for expected_index in expected_indexes:
            assert expected_index in index_names


@pytest.mark.django_db
class TestEnquiryHistory:
    """Test EnquiryHistory model."""
    
    def test_enquiry_history_creation(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        history = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Test note',
            created_by=user
        )
        
        assert history.enquiry == enquiry
        assert history.note == 'Test note'
        assert history.created_by == user
        assert history.created_at is not None
        assert history._meta.db_table == 'members_app_enquiryhistory'
    
    def test_enquiry_history_str_method(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        history = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Test note',
            created_by=user
        )
        
        assert str(history) == f"History for Test Enquiry at {history.created_at}"
    
    def test_enquiry_history_save_updates_enquiry(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member,
            status='new'  # Manually set to 'new' to test the status change logic
        )

        original_updated_at = enquiry.updated_at
        original_status = enquiry.status
        
        # Add a small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        # Create history entry
        history = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Test note',
            created_by=user
        )
        
        # Refresh enquiry from database
        enquiry.refresh_from_db()
        
        # Check that updated_at was changed (or at least not less than original)
        assert enquiry.updated_at >= original_updated_at
        
        # Check that status changed from 'new' to 'open'
        assert original_status == 'new'
        assert enquiry.status == 'open'
    
    def test_enquiry_history_relationship(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        history = EnquiryHistory.objects.create(
            enquiry=enquiry,
            note='Test note',
            created_by=user
        )
        
        # Test reverse relationship
        assert history in enquiry.history.all()
    
    def test_enquiry_history_indexes(self):
        indexes = EnquiryHistory._meta.indexes
        index_names = [idx.name for idx in indexes]
        
        assert 'history_enquiry_created_idx' in index_names


@pytest.mark.django_db
class TestContact:
    """Test Contact model."""
    
    def test_contact_creation(self):
        department = Department.objects.create(name='Test Department')
        section = Section.objects.create(name='Test Section', department=department)
        area = Area.objects.create(name='Test Area')
        jobtype = JobType.objects.create(name='Test Job Type')
        
        contact = Contact.objects.create(
            name='Test Contact',
            description='Test Description',
            telephone_number='123456789',
            section=section
        )
        contact.areas.add(area)
        contact.job_types.add(jobtype)
        
        assert contact.name == 'Test Contact'
        assert contact.description == 'Test Description'
        assert contact.telephone_number == '123456789'
        assert contact.section == section
        assert area in contact.areas.all()
        assert jobtype in contact.job_types.all()
        assert str(contact) == 'Test Contact'
        assert contact._meta.db_table == 'members_app_contact'
    
    def test_contact_name_unique(self):
        department = Department.objects.create(name='Test Department')
        section = Section.objects.create(name='Test Section', department=department)
        
        Contact.objects.create(
            name='Unique Contact',
            telephone_number='123456789',
            section=section
        )
        
        with pytest.raises(IntegrityError):
            Contact.objects.create(
                name='Unique Contact',
                telephone_number='987654321',
                section=section
            )
    
    def test_contact_relationships(self):
        department = Department.objects.create(name='Test Department')
        section = Section.objects.create(name='Test Section', department=department)
        area = Area.objects.create(name='Test Area')
        jobtype = JobType.objects.create(name='Test Job Type')
        
        contact = Contact.objects.create(
            name='Test Contact',
            telephone_number='123456789',
            section=section
        )
        contact.areas.add(area)
        contact.job_types.add(jobtype)
        
        # Test reverse relationships
        assert contact in section.contacts.all()
        assert contact in area.contacts.all()
        assert contact in jobtype.contacts.all()


@pytest.mark.django_db
class TestReferenceSequence:
    """Test ReferenceSequence model and reference generation."""

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
        expected = f'MEM-{current_year:02d}-0001'
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
        expected = f'MEM-{current_year:02d}-0005'
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

        expected_refs = [f'MEM-{current_year:02d}-{i:04d}' for i in range(1, 6)]
        assert references == expected_refs

    def test_reference_generation_with_existing_enquiry(self):
        """Test that reference generation skips existing references."""
        current_year = timezone.now().year % 100

        # Create user and member for enquiry
        user = User.objects.create_user(username='test_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )

        # Create an enquiry with a specific reference
        existing_ref = f'MEM-{current_year:02d}-0001'
        Enquiry.objects.create(
            title='Existing Enquiry',
            description='Test',
            member=member,
            reference=existing_ref
        )

        # Set sequence to generate the same number
        ReferenceSequence.objects.create(year=current_year, next_number=1)

        # Should skip the existing reference
        new_reference = ReferenceSequence.get_next_reference()
        expected = f'MEM-{current_year:02d}-0002'
        assert new_reference == expected


@pytest.mark.django_db
class TestEnquiryAttachment:
    """Test EnquiryAttachment model."""
    
    def test_enquiry_attachment_creation(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename='test.jpg',
            file_path='attachments/test.jpg',
            file_size=1024,
            uploaded_by=user
        )
        
        assert attachment.enquiry == enquiry
        assert attachment.filename == 'test.jpg'
        assert attachment.file_path == 'attachments/test.jpg'
        assert attachment.file_size == 1024
        assert attachment.uploaded_by == user
        assert attachment.uploaded_at is not None
        assert attachment._meta.db_table == 'members_app_enquiryattachment'
    
    def test_enquiry_attachment_str_method(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member,
            reference='MEM-24-0001'
        )
        
        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename='test.jpg',
            file_path='attachments/test.jpg',
            file_size=1024,
            uploaded_by=user
        )
        
        assert str(attachment) == 'test.jpg - MEM-24-0001'
    
    def test_enquiry_attachment_file_url_property(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename='test.jpg',
            file_path='attachments/test.jpg',
            file_size=1024,
            uploaded_by=user
        )
        
        # Mock settings.MEDIA_URL for the test
        from unittest.mock import patch
        with patch('django.conf.settings.MEDIA_URL', '/media/'):
            assert attachment.file_url == '/media/attachments/test.jpg'
    
    def test_enquiry_attachment_relationship(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename='test.jpg',
            file_path='attachments/test.jpg',
            file_size=1024,
            uploaded_by=user
        )
        
        # Test reverse relationship
        assert attachment in enquiry.attachments.all()
    
    def test_enquiry_attachment_cascade_delete(self):
        user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        attachment = EnquiryAttachment.objects.create(
            enquiry=enquiry,
            filename='test.jpg',
            file_path='attachments/test.jpg',
            file_size=1024,
            uploaded_by=user
        )
        
        attachment_id = attachment.id
        
        # Delete enquiry should cascade to attachment
        enquiry.delete()
        
        assert not EnquiryAttachment.objects.filter(id=attachment_id).exists()
    
    def test_enquiry_attachment_indexes(self):
        indexes = EnquiryAttachment._meta.indexes
        index_names = [idx.name for idx in indexes]
        
        assert 'attachment_idx' in index_names


@pytest.mark.django_db
class TestAudit:
    """Test Audit model."""
    
    def test_audit_creation(self):
        user = User.objects.create_user(username='test_user')
        member_user = User.objects.create_user(username='member_user')
        ward = Ward.objects.create(name='Test Ward')
        member = Member.objects.create(
            first_name='Test',
            last_name='Member',
            email=f'test.member{uuid.uuid4().hex[:8]}@example.com',
            ward=ward
        )
        
        enquiry = Enquiry.objects.create(
            title='Test Enquiry',
            description='Test Description',
            member=member
        )
        
        audit = Audit.objects.create(
            user=user,
            enquiry=enquiry,
            action_details='Test action',
            ip_address='127.0.0.1'
        )
        
        assert audit.user == user
        assert audit.enquiry == enquiry
        assert audit.action_details == 'Test action'
        assert audit.ip_address == '127.0.0.1'
        assert audit.action_datetime is not None
        assert audit._meta.db_table == 'members_app_audit'
    
    def test_audit_nullable_fields(self):
        # Test that user and enquiry can be null
        audit = Audit.objects.create(
            action_details='Test action without user/enquiry'
        )
        
        assert audit.user is None
        assert audit.enquiry is None
        assert audit.action_details == 'Test action without user/enquiry'