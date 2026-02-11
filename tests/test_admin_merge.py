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
Test admin merge functionality for contacts and job types.
"""

import pytest
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.http import HttpRequest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore

from application.models import (
    Contact,
    JobType,
    Enquiry,
    Section,
    Department,
    Member,
    Ward,
    Admin,
)
from application.admin import (
    ContactAdmin,
    JobTypeAdmin,
    MemberAdmin,
    merge_contacts,
    merge_job_types,
    merge_members,
)


@pytest.mark.django_db
class TestContactMerge:
    """Test contact merge functionality."""

    def setup_method(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Create test department and section
        self.department = Department.objects.create(name="Test Department")
        self.section = Section.objects.create(
            name="Test Section", department=self.department
        )

        # Create test contacts
        self.contact1 = Contact.objects.create(
            name="Contact 1", section=self.section, email="contact1@test.com"
        )
        self.contact2 = Contact.objects.create(
            name="Contact 2", section=self.section, email="contact2@test.com"
        )

        # Create test job types
        self.job_type1 = JobType.objects.create(name="Job Type 1")
        self.job_type2 = JobType.objects.create(name="Job Type 2")

        # Add job types to contacts
        self.contact1.job_types.add(self.job_type1)
        self.contact2.job_types.add(self.job_type2)

        # Create test member for enquiries
        self.ward = Ward.objects.create(name="Test Ward")
        self.member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email="member@test.com",
            ward=self.ward,
        )

        # Create test enquiries
        self.enquiry1 = Enquiry.objects.create(
            title="Test Enquiry 1", member=self.member, contact=self.contact1
        )
        self.enquiry2 = Enquiry.objects.create(
            title="Test Enquiry 2", member=self.member, contact=self.contact2
        )

        # Set up admin request mock
        self.request = self._setup_request()
        self.admin_site = AdminSite()
        self.contact_admin = ContactAdmin(Contact, self.admin_site)

    def _setup_request(self):
        """Set up a mock request with messages and session."""
        request = HttpRequest()
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_merge_contacts_success(self):
        """Test successful contact merge."""
        # Ensure contact1 has lower ID (will be kept)
        if self.contact1.id > self.contact2.id:
            self.contact1, self.contact2 = self.contact2, self.contact1
            # Update enquiries accordingly
            self.enquiry1.contact = self.contact1
            self.enquiry1.save()
            self.enquiry2.contact = self.contact2
            self.enquiry2.save()

        # Get initial job types for contact1
        contact1_job_types = set(self.contact1.job_types.all())
        contact2_job_types = set(self.contact2.job_types.all())

        # Execute merge
        queryset = Contact.objects.filter(id__in=[self.contact1.id, self.contact2.id])
        merge_contacts(self.contact_admin, self.request, queryset)

        # Verify contact2 is deleted
        assert not Contact.objects.filter(id=self.contact2.id).exists()

        # Verify contact1 still exists
        contact1_after = Contact.objects.get(id=self.contact1.id)
        assert contact1_after.name == self.contact1.name

        # Verify job types were merged
        merged_job_types = set(contact1_after.job_types.all())
        expected_job_types = contact1_job_types.union(contact2_job_types)
        assert merged_job_types == expected_job_types

        # Verify enquiries were moved
        self.enquiry1.refresh_from_db()
        self.enquiry2.refresh_from_db()
        assert self.enquiry1.contact == contact1_after
        assert self.enquiry2.contact == contact1_after

    def test_merge_contacts_wrong_count(self):
        """Test merge fails with wrong number of contacts."""
        # Test with 1 contact
        queryset = Contact.objects.filter(id=self.contact1.id)
        merge_contacts(self.contact_admin, self.request, queryset)

        # Verify both contacts still exist
        assert Contact.objects.filter(id=self.contact1.id).exists()
        assert Contact.objects.filter(id=self.contact2.id).exists()

        # Test with 3 contacts
        contact3 = Contact.objects.create(name="Contact 3", section=self.section)
        queryset = Contact.objects.filter(
            id__in=[self.contact1.id, self.contact2.id, contact3.id]
        )
        merge_contacts(self.contact_admin, self.request, queryset)

        # Verify all contacts still exist
        assert Contact.objects.filter(id=self.contact1.id).exists()
        assert Contact.objects.filter(id=self.contact2.id).exists()
        assert Contact.objects.filter(id=contact3.id).exists()


@pytest.mark.django_db
class TestJobTypeMerge:
    """Test job type merge functionality."""

    def setup_method(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Create test job types
        self.job_type1 = JobType.objects.create(name="Job Type 1")
        self.job_type2 = JobType.objects.create(name="Job Type 2")

        # Create test department, section and contacts
        self.department = Department.objects.create(name="Test Department")
        self.section = Section.objects.create(
            name="Test Section", department=self.department
        )
        self.contact1 = Contact.objects.create(name="Contact 1", section=self.section)
        self.contact2 = Contact.objects.create(name="Contact 2", section=self.section)

        # Associate job types with contacts
        self.contact1.job_types.add(self.job_type1)
        self.contact2.job_types.add(self.job_type2)

        # Create test member for enquiries
        self.ward = Ward.objects.create(name="Test Ward")
        self.member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email="member@test.com",
            ward=self.ward,
        )

        # Create test enquiries
        self.enquiry1 = Enquiry.objects.create(
            title="Test Enquiry 1", member=self.member, job_type=self.job_type1
        )
        self.enquiry2 = Enquiry.objects.create(
            title="Test Enquiry 2", member=self.member, job_type=self.job_type2
        )

        # Set up admin request mock
        self.request = self._setup_request()
        self.admin_site = AdminSite()
        self.job_type_admin = JobTypeAdmin(JobType, self.admin_site)

    def _setup_request(self):
        """Set up a mock request with messages and session."""
        request = HttpRequest()
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_merge_job_types_success(self):
        """Test successful job type merge."""
        # Ensure job_type1 has lower ID (will be kept)
        if self.job_type1.id > self.job_type2.id:
            self.job_type1, self.job_type2 = self.job_type2, self.job_type1
            # Update references accordingly
            self.enquiry1.job_type = self.job_type1
            self.enquiry1.save()
            self.enquiry2.job_type = self.job_type2
            self.enquiry2.save()
            self.contact1.job_types.clear()
            self.contact1.job_types.add(self.job_type1)
            self.contact2.job_types.clear()
            self.contact2.job_types.add(self.job_type2)

        # Execute merge
        queryset = JobType.objects.filter(id__in=[self.job_type1.id, self.job_type2.id])
        merge_job_types(self.job_type_admin, self.request, queryset)

        # Verify job_type2 is deleted
        assert not JobType.objects.filter(id=self.job_type2.id).exists()

        # Verify job_type1 still exists
        job_type1_after = JobType.objects.get(id=self.job_type1.id)
        assert job_type1_after.name == self.job_type1.name

        # Verify enquiries were moved
        self.enquiry1.refresh_from_db()
        self.enquiry2.refresh_from_db()
        assert self.enquiry1.job_type == job_type1_after
        assert self.enquiry2.job_type == job_type1_after

        # Verify contacts were updated
        self.contact1.refresh_from_db()
        self.contact2.refresh_from_db()
        assert job_type1_after in self.contact1.job_types.all()
        assert job_type1_after in self.contact2.job_types.all()

    def test_merge_job_types_wrong_count(self):
        """Test merge fails with wrong number of job types."""
        # Test with 1 job type
        queryset = JobType.objects.filter(id=self.job_type1.id)
        merge_job_types(self.job_type_admin, self.request, queryset)

        # Verify both job types still exist
        assert JobType.objects.filter(id=self.job_type1.id).exists()
        assert JobType.objects.filter(id=self.job_type2.id).exists()

        # Test with 3 job types
        job_type3 = JobType.objects.create(name="Job Type 3")
        queryset = JobType.objects.filter(
            id__in=[self.job_type1.id, self.job_type2.id, job_type3.id]
        )
        merge_job_types(self.job_type_admin, self.request, queryset)

        # Verify all job types still exist
        assert JobType.objects.filter(id=self.job_type1.id).exists()
        assert JobType.objects.filter(id=self.job_type2.id).exists()
        assert JobType.objects.filter(id=job_type3.id).exists()


@pytest.mark.django_db
class TestMemberMerge:
    """Test member merge functionality."""

    def setup_method(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Create test ward
        self.ward = Ward.objects.create(name="Test Ward")

        # Create test members
        self.member1 = Member.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@test.com",
            ward=self.ward,
            is_active=True,
        )
        self.member2 = Member.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@test.com",
            ward=self.ward,
            is_active=True,
        )

        # Create test enquiries
        self.enquiry1 = Enquiry.objects.create(
            title="Test Enquiry 1", member=self.member1
        )
        self.enquiry2 = Enquiry.objects.create(
            title="Test Enquiry 2", member=self.member2
        )

        # Set up admin request mock
        self.request = self._setup_request()
        self.admin_site = AdminSite()
        self.member_admin = MemberAdmin(Member, self.admin_site)

    def _setup_request(self):
        """Set up a mock request with messages and session."""
        request = HttpRequest()
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_merge_members_success(self):
        """Test successful member merge."""
        # Ensure member1 has lower ID (will be kept)
        if self.member1.id > self.member2.id:
            self.member1, self.member2 = self.member2, self.member1
            # Update enquiries accordingly
            self.enquiry1.member = self.member1
            self.enquiry1.save()
            self.enquiry2.member = self.member2
            self.enquiry2.save()

        # Execute merge
        queryset = Member.objects.filter(id__in=[self.member1.id, self.member2.id])
        merge_members(self.member_admin, self.request, queryset)

        # Verify member2 is deleted
        assert not Member.objects.filter(id=self.member2.id).exists()

        # Verify member1 still exists
        member1_after = Member.objects.get(id=self.member1.id)
        assert member1_after.first_name == self.member1.first_name
        assert member1_after.last_name == self.member1.last_name

        # Verify enquiries were moved
        self.enquiry1.refresh_from_db()
        self.enquiry2.refresh_from_db()
        assert self.enquiry1.member == member1_after
        assert self.enquiry2.member == member1_after

    def test_merge_members_wrong_count(self):
        """Test merge fails with wrong number of members."""
        # Test with 1 member
        queryset = Member.objects.filter(id=self.member1.id)
        merge_members(self.member_admin, self.request, queryset)

        # Verify both members still exist
        assert Member.objects.filter(id=self.member1.id).exists()
        assert Member.objects.filter(id=self.member2.id).exists()

        # Test with 3 members
        member3 = Member.objects.create(
            first_name="Bob",
            last_name="Johnson",
            email="bob.johnson@test.com",
            ward=self.ward,
            is_active=True,
        )
        queryset = Member.objects.filter(
            id__in=[self.member1.id, self.member2.id, member3.id]
        )
        merge_members(self.member_admin, self.request, queryset)

        # Verify all members still exist
        assert Member.objects.filter(id=self.member1.id).exists()
        assert Member.objects.filter(id=self.member2.id).exists()
        assert Member.objects.filter(id=member3.id).exists()
