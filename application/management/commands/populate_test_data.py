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
Django management command to populate the database with test data.

This command creates sample members, wards, departments, contacts, and job types
that can be used for testing and development without manually entering data.

Usage:
    python manage.py populate_test_data
"""

from django.core.management.base import BaseCommand
from application.models import Ward, Department, Section, Contact, Member, JobType, Area


class Command(BaseCommand):
    help = "Populate database with test data for development and testing"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting database population..."))

        # Create Wards
        self.stdout.write("Creating wards...")
        wards = []
        ward_names = [
            "Civic Centre Ward",
            "Riverside Ward",
            "Hillside Ward",
            "Park Lane Ward",
            "Green Valley Ward",
            "North Gate Ward",
            "South Gate Ward",
        ]
        for name in ward_names:
            ward, created = Ward.objects.get_or_create(name=name)
            wards.append(ward)
            if created:
                self.stdout.write(f"  Created ward: {name}")

        # Create Areas
        self.stdout.write("Creating areas...")
        areas = []
        area_names = [
            "Town Centre",
            "Riverside",
            "North District",
            "South District",
            "East Side",
            "West Side",
        ]
        for name in area_names:
            area, created = Area.objects.get_or_create(name=name)
            areas.append(area)
            if created:
                self.stdout.write(f"  Created area: {name}")

        # Create Departments
        self.stdout.write("Creating departments...")
        departments = []
        dept_names = [
            "Planning",
            "Highways",
            "Environmental Services",
            "Housing",
            "Council Tax",
            "Licensing",
            "Democratic Services",
        ]
        for name in dept_names:
            dept, created = Department.objects.get_or_create(name=name)
            departments.append(dept)
            if created:
                self.stdout.write(f"  Created department: {name}")

        # Create Sections
        self.stdout.write("Creating sections...")
        sections_data = [
            ("Building Control", departments[0]),  # Planning
            ("Planning Applications", departments[0]),  # Planning
            ("Road Maintenance", departments[1]),  # Highways
            ("Street Cleaning", departments[2]),  # Environmental Services
            ("Housing Benefits", departments[3]),  # Housing
            ("Maintenance", departments[3]),  # Housing
            ("Billing", departments[4]),  # Council Tax
            ("Premises", departments[5]),  # Licensing
        ]
        sections = []
        for section_name, dept in sections_data:
            section, created = Section.objects.get_or_create(
                name=section_name, department=dept
            )
            sections.append(section)
            if created:
                self.stdout.write(f"  Created section: {section_name}")

        # Create Job Types
        self.stdout.write("Creating job types...")
        job_types = []
        job_type_names = [
            "Pothole Repair",
            "Planning Query",
            "Housing Issue",
            "Street Light Repair",
            "Fly Tipping Report",
            "Recycling Query",
            "Parking Issue",
            "Waste Collection",
            "Building Complaint",
        ]
        for name in job_type_names:
            job_type, created = JobType.objects.get_or_create(name=name)
            job_types.append(job_type)
            if created:
                self.stdout.write(f"  Created job type: {name}")

        # Create Contacts
        self.stdout.write("Creating contacts...")
        contacts_data = [
            (
                "Planning Enquiries",
                sections[1],
                [job_types[1]],
            ),  # Planning Applications section
            (
                "Highways Maintenance",
                sections[2],
                [job_types[0], job_types[3]],
            ),  # Road Maintenance section
            (
                "Environmental Services",
                sections[3],
                [job_types[4], job_types[5]],
            ),  # Street Cleaning section
            (
                "Housing Support",
                sections[4],
                [job_types[2]],
            ),  # Housing Benefits section
            (
                "Waste Collection",
                sections[3],
                [job_types[7]],
            ),  # Street Cleaning section
            ("Street Licensing", sections[7], [job_types[6]]),  # Premises section
        ]
        for i, (name, section, jt_list) in enumerate(contacts_data):
            contact, created = Contact.objects.get_or_create(
                name=name,
                defaults={
                    "section": section,
                    "email": f'{name.lower().replace(" ", ".")}@council.local',
                    "telephone_number": f"01632 96{000 + i:04d}",
                    "description": f"Contact for {name}",
                },
            )
            if created:
                # Add areas and job types
                contact.areas.set(areas[i % len(areas) : i % len(areas) + 2])
                contact.job_types.set(jt_list)
                self.stdout.write(f"  Created contact: {name}")

        # Create Members
        self.stdout.write("Creating members...")
        members_data = [
            ("John", "Smith", "john.smith@parliament.uk"),
            ("Sarah", "Johnson", "sarah.johnson@parliament.uk"),
            ("Michael", "Williams", "michael.williams@parliament.uk"),
            ("Emma", "Brown", "emma.brown@parliament.uk"),
            ("David", "Jones", "david.jones@parliament.uk"),
            ("Lucy", "Garcia", "lucy.garcia@parliament.uk"),
            ("Robert", "Miller", "robert.miller@parliament.uk"),
            ("Jennifer", "Davis", "jennifer.davis@parliament.uk"),
            ("James", "Taylor", "james.taylor@parliament.uk"),
            ("Rachel", "Anderson", "rachel.anderson@parliament.uk"),
            ("Thomas", "Thomas", "thomas.thomas@parliament.uk"),
            ("Victoria", "Moore", "victoria.moore@parliament.uk"),
        ]
        for first_name, last_name, email in members_data:
            # Assign to random wards
            ward = wards[(ord(first_name[0]) - ord("A")) % len(wards)]
            member, created = Member.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "ward": ward,
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"  Created member: {first_name} {last_name}")

        self.stdout.write(
            self.style.SUCCESS(
                "\nDatabase population complete!\n"
                "You can now:\n"
                "  1. Log in with Azure AD\n"
                "  2. Create enquiries using the test members and other data\n"
                "  3. Test the application workflow\n"
            )
        )
