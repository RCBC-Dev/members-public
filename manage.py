#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from dotenv import load_dotenv


def main():
    """Run administrative tasks."""
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(f"Loaded environment variables from: {dotenv_path}")
    else:
        print("Warning: .env file not found. Environment variables may be missing.")

    # Determine and show the settings module based on ENVIRONMENT in .env
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    if not settings_module:
        if environment == "production":
            settings_module = "project.settings.production"
        elif environment == "test":
            settings_module = "project.settings.test"
        elif environment == "development" or environment == "dev":
            settings_module = "project.settings.development"
        else:
            settings_module = "project.settings.development"
            if environment:
                print(
                    f"Warning: Unrecognized ENVIRONMENT '{environment}', defaulting to development settings."
                )
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
        print(
            f"No DJANGO_SETTINGS_MODULE set. Using ENVIRONMENT variable: {environment.upper() or 'DEVELOPMENT'}"
        )
        print(f"DJANGO_SETTINGS_MODULE set to: {settings_module}")
    else:
        print(f"DJANGO_SETTINGS_MODULE: {settings_module}")

    # Print a banner based on which settings are in use
    if settings_module.endswith("production"):
        print("\n=== USING PRODUCTION SETTINGS ===\n")
    elif settings_module.endswith("test"):
        print("\n=== USING TEST SETTINGS ===\n")
    elif settings_module.endswith("development"):
        print("\n=== USING DEVELOPMENT SETTINGS ===\n")
    else:
        print("\n=== USING CUSTOM/UNKNOWN SETTINGS ===\n")

    # Print key environment variables for debugging
    for key in [
        "DBNAME",
        "DBUSER",
        "DBHOST",
        "DBPORT",
        "DJANGO_SECRET_KEY",
        "ENV",
        "DEBUG",
        "ALLOWED_HOSTS",
        "STATIC_ROOT",
    ]:
        value = os.environ.get(key)
        if value:
            print(f"{key} = {value}")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
