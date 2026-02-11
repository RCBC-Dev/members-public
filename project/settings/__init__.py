"""
Settings package initialization.
By default, this will import the development settings.
To use a different settings file, set the DJANGO_SETTINGS_MODULE environment variable.
"""

import os
import sys

DEV_SETTINGS_MODULE = "project.settings.development"

# Default to development settings
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", DEV_SETTINGS_MODULE)

if settings_module == "project.settings":
    # If the old settings module is specified, redirect to the new one
    os.environ["DJANGO_SETTINGS_MODULE"] = DEV_SETTINGS_MODULE
    settings_module = DEV_SETTINGS_MODULE

# Import the specified settings module
if settings_module == DEV_SETTINGS_MODULE:
    from .development import *
elif settings_module == "project.settings.test":
    from .test import *
elif settings_module == "project.settings.production":
    from .production import *
else:
    # Default to development settings if an unknown module is specified
    from .development import *
