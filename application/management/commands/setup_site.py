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

from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings


class Command(BaseCommand):
    help = 'Set up the Site object with the correct domain'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            help='Domain name for the site (e.g., localhost:8000 or yourdomain.com)',
        )

    def handle(self, *args, **options):
        domain = options.get('domain') or getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
        
        site, created = Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={
                'domain': domain,
                'name': domain
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created Site object with domain: {domain}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Updated Site object with domain: {domain}')
            )
