"""
Context processors for the assets app.
"""
import os
from django.conf import settings
from project.version import get_version, get_latest_changes

def version_info(request):
    """
    Add version and environment information to the template context.
    """
    # Get database configuration
    db_config = settings.DATABASES.get('default', {})
    db_name = db_config.get('NAME')
    db_server = db_config.get('HOST')
    
    # Determine environment
    # Check if environment variable is set to TEST or PRODUCTION
    environment = os.environ.get('ENVIRONMENT', '').upper()
    
    # Default to DEVELOPMENT unless explicitly set to TEST or PRODUCTION
    if environment not in ['TEST', 'PRODUCTION']:
        environment = 'DEVELOPMENT'
    
    return {
        'version': get_version(),
        'change_log': get_latest_changes(None),  # Send all changes, slice in template
        'db_name': db_name,
        'db_server': db_server,
        'environment': environment,
    }

