"""
Version information for the Members Enquiries System.
"""

# Version format: MAJOR.MINOR
# - MAJOR: Significant changes that may require data migration or affect compatibility
# - MINOR: Incremented for each release with minor changes or bug fixes

VERSION = "1.04"

# Change log entries should be in the format:
# (version, date, description)
CHANGE_LOG = [
    ("1.04", "2026-02-09", "Add db.sqlite3 to .gitignore - database files should not be committed"),

    ("1.03", "2026-02-09", "Updated README.md with Deployment/DB Options"),

    ("1.02", "2026-02-09", "Removed somre references to RCBC in places like footer, added some screenshots to the README.md added .gitkeep for the logs folder"),

    ("1.01", "2026-02-09", "Added management command to populate DB with 'test data'"),

    ("1.00", "2025-06-11", "Initial Public Release"),
]


def get_version():
    """Return the current version number."""
    return VERSION


def get_change_log():
    """Return the change log as a list of tuples (version, date, description)."""
    return CHANGE_LOG


def get_latest_changes(count=5):
    """Return the most recent changes from the change log."""
    if count is None:
        return CHANGE_LOG  # Return all changes
    return CHANGE_LOG[:count]
