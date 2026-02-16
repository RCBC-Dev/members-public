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
Additional tests for uncovered model methods.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.utils import timezone

from application.models import (
    Admin,
    Department,
    Enquiry,
    EnquiryHistory,
    UserMapping,
    Member,
    Ward,
    Section,
    Area,
    JobType,
)


def _make_user(username="legacy_user"):
    return User.objects.create_user(username=username, password="pass")


def _make_section(name="Test Section"):
    dept, _ = Department.objects.get_or_create(name="Test Dept")
    section, _ = Section.objects.get_or_create(name=name, defaults={"department": dept})
    return section


_member_counter = 0


def _make_member(tag="test"):
    global _member_counter
    _member_counter += 1
    ward, _ = Ward.objects.get_or_create(name="Test Ward")
    member = Member.objects.create(
        first_name="Test",
        last_name=f"Member {_member_counter}",
        email=f"member{_member_counter}_{tag}@example.com",
        ward=ward,
    )
    return member


@pytest.mark.django_db
class TestUserMappingStr:
    """Tests for UserMapping.__str__."""

    def _setup_users_and_mapping(self, is_primary=True):
        legacy = User.objects.create_user(username="legacy_u", password="p")
        sso = User.objects.create_user(username="sso_u", password="p")
        mapping = UserMapping(
            legacy_user=legacy,
            sso_user=sso,
            is_primary_mapping=is_primary,
        )
        return mapping

    def test_str_primary_mapping(self):
        mapping = self._setup_users_and_mapping(is_primary=True)
        result = str(mapping)
        assert "legacy_u" in result
        assert "sso_u" in result
        assert "(Primary)" in result

    def test_str_non_primary_mapping(self):
        mapping = self._setup_users_and_mapping(is_primary=False)
        result = str(mapping)
        assert "legacy_u" in result
        assert "sso_u" in result
        assert "(Primary)" not in result


@pytest.mark.django_db
class TestUserMappingApplyToEnquiries:
    """Tests for UserMapping.apply_to_enquiries."""

    def _make_enquiry(self, admin=None):
        section = _make_section("ApplySection")
        member = _make_member("apply")
        return Enquiry.objects.create(
            title="Test Enquiry",
            member=member,
            section=section,
            status="open",
            admin=admin,
        )

    def test_non_primary_mapping_returns_zero(self):
        legacy = User.objects.create_user(username="legacy2", password="p")
        sso = User.objects.create_user(username="sso2", password="p")
        mapping = UserMapping.objects.create(
            legacy_user=legacy, sso_user=sso, is_primary_mapping=False
        )
        result = mapping.apply_to_enquiries()
        assert result == 0

    def test_primary_mapping_with_no_data_returns_zero(self):
        legacy = User.objects.create_user(username="legacy3", password="p")
        sso = User.objects.create_user(username="sso3", password="p")
        mapping = UserMapping.objects.create(
            legacy_user=legacy, sso_user=sso, is_primary_mapping=True
        )
        result = mapping.apply_to_enquiries()
        assert result == 0

    def test_primary_mapping_updates_enquiries(self):
        legacy = User.objects.create_user(username="legacy4", password="p")
        sso = User.objects.create_user(username="sso4", password="p")
        legacy_admin = Admin.objects.create(user=legacy)
        mapping = UserMapping.objects.create(
            legacy_user=legacy, sso_user=sso, is_primary_mapping=True
        )
        enq = self._make_enquiry(admin=legacy_admin)
        result = mapping.apply_to_enquiries()
        # Enquiry was re-assigned to new admin
        enq.refresh_from_db()
        new_admin = Admin.objects.get(user=sso)
        assert enq.admin == new_admin
        assert result > 0


@pytest.mark.django_db
class TestEnquirySave:
    """Tests for Enquiry.save() edge cases."""

    def _make_enquiry_kwargs(self):
        section = _make_section("Sec Save")
        member = _make_member("save")
        return {"title": "Save Test", "member": member, "section": section}

    def test_new_enquiry_gets_open_status(self):
        kwargs = self._make_enquiry_kwargs()
        enq = Enquiry(**kwargs)
        enq.save()
        assert enq.status == "open"

    def test_new_enquiry_with_creating_user_admin_auto_assigned(self):
        kwargs = self._make_enquiry_kwargs()
        user = User.objects.create_user(username="creator_admin", password="p")
        admin = Admin.objects.create(user=user)
        enq = Enquiry(**kwargs)
        enq._creating_user = user
        enq.save()
        assert enq.admin == admin

    def test_new_enquiry_with_creating_user_non_admin_unassigned(self):
        kwargs = self._make_enquiry_kwargs()
        user = User.objects.create_user(username="non_admin_creator", password="p")
        enq = Enquiry(**kwargs)
        enq._creating_user = user
        enq.save()
        assert enq.admin is None

    def test_closing_enquiry_sets_closed_at(self):
        kwargs = self._make_enquiry_kwargs()
        enq = Enquiry.objects.create(**kwargs)
        assert enq.closed_at is None
        enq.status = "closed"
        enq.save()
        assert enq.closed_at is not None

    def test_reopening_enquiry_clears_closed_at(self):
        kwargs = self._make_enquiry_kwargs()
        enq = Enquiry.objects.create(**kwargs)
        enq.status = "closed"
        enq.save()
        assert enq.closed_at is not None
        enq.status = "open"
        enq.save()
        assert enq.closed_at is None


@pytest.mark.django_db
class TestEnquiryDueDate:
    """Tests for Enquiry.due_date property."""

    def _make_enquiry(self):
        section = _make_section("Sec Due")
        member = _make_member("due")
        return Enquiry.objects.create(
            title="Due Date Test",
            member=member,
            section=section,
            status="open",
        )

    def test_due_date_returns_datetime(self):
        enq = self._make_enquiry()
        result = enq.due_date
        assert result is not None
        assert hasattr(result, "date")

    def test_due_date_fallback_when_calculation_returns_none(self):
        enq = self._make_enquiry()
        with patch(
            "application.utils.calculate_working_days_due_date", return_value=None
        ):
            result = enq.due_date
        # Should fall back to created_at + 5 days
        expected = enq.created_at + timezone.timedelta(days=5)
        assert abs((result - expected).total_seconds()) < 5


@pytest.mark.django_db
class TestEnquiryHistoryMethods:
    """Tests for EnquiryHistory.get_note_type_icon and get_note_type_color."""

    def _make_history(self, note_type):
        section = _make_section("Hist Section")
        member = _make_member("hist")
        enq = Enquiry.objects.create(
            title=f"Hist {note_type}",
            member=member,
            section=section,
            status="open",
        )
        user, _ = User.objects.get_or_create(
            username="hist_user", defaults={"password": "p"}
        )
        history = EnquiryHistory(
            enquiry=enq,
            note="Test note",
            note_type=note_type,
            created_by=user,
        )
        return history

    def test_get_note_type_icon_known_type(self):
        h = self._make_history("general")
        assert h.get_note_type_icon() == "bi-chat-text"

    def test_get_note_type_icon_email_incoming(self):
        h = self._make_history("email_incoming")
        assert h.get_note_type_icon() == "email-incoming-icon"

    def test_get_note_type_icon_unknown_returns_default(self):
        h = self._make_history("unknown_type")
        assert h.get_note_type_icon() == "bi-chat-text"

    def test_get_note_type_color_phoned_contact(self):
        h = self._make_history("phoned_contact")
        assert h.get_note_type_color() == "text-success"

    def test_get_note_type_color_enquiry_edited(self):
        h = self._make_history("enquiry_edited")
        assert h.get_note_type_color() == "text-danger"

    def test_get_note_type_color_unknown_returns_default(self):
        h = self._make_history("bogus_type")
        assert h.get_note_type_color() == "text-secondary"

    def test_all_note_types_have_icon(self):
        note_types = [nt[0] for nt in EnquiryHistory.NOTE_TYPE_CHOICES]
        h = self._make_history("general")
        for nt in note_types:
            h.note_type = nt
            icon = h.get_note_type_icon()
            assert isinstance(icon, str) and len(icon) > 0

    def test_all_note_types_have_color(self):
        note_types = [nt[0] for nt in EnquiryHistory.NOTE_TYPE_CHOICES]
        h = self._make_history("general")
        for nt in note_types:
            h.note_type = nt
            color = h.get_note_type_color()
            assert isinstance(color, str) and len(color) > 0
