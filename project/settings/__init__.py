"""
Settings package initialization.
By default, this will import the development settings.
To use a different settings file, set the DJANGO_SETTINGS_MODULE environment variable.
"""

import os
import sys

# Default to development settings
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'project.settings.development')

if settings_module == 'project.settings':
    # If the old settings module is specified, redirect to the new one
    os.environ['DJANGO_SETTINGS_MODULE'] = 'project.settings.development'
    settings_module = 'project.settings.development'

# Import the specified settings module
if settings_module == 'project.settings.development':
    from .development import *
elif settings_module == 'project.settings.test':
    from .test import *
elif settings_module == 'project.settings.production':
    from .production import *
else:
    # Default to development settings if an unknown module is specified
    from .development import *
