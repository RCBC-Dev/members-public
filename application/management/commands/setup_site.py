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
