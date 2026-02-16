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
Version information for the Members Enquiries System.
"""

# Version format: MAJOR.MINOR
# - MAJOR: Significant changes that may require data migration or affect compatibility
# - MINOR: Incremented for each release with minor changes or bug fixes

VERSION = "1.10"

# Change log entries should be in the format:
# (version, date, description)
CHANGE_LOG = [
    ("1.10", "2026-02-16", "Fixed some discrepancies in the README.md - updated production and test settings files to be database agnostic"),

    (
        "1.09",
        "2026-02-16",
        "Added SonarQube Quality Gate reports to README.md - some changes to README in relation to .env variables",
    ),
    ("1.08", "2026-02-12", "Added new tests to get QualityGate Pass in SonarQube"),
    (
        "1.07",
        "2026-02-11",
        "Some refactoring after plugging back into SonarQube - used Opus4.6 to run parallel refactoring/fixes using up to 11 agents simultaneously, without a single error/test failure",
    ),
    (
        "1.06",
        "2026-02-11",
        "Renamed a function for image optimisation as the project no longer uses summernote",
    ),
    (
        "1.05",
        "2026-02-11",
        "Updated settings and templates to use .env variables for COUNCIL_NAME, DOMAIN, updated the model choices for Service Types to use 3rd Party, rather than 'Not RCBC' reflected in templates",
    ),
    (
        "1.04",
        "2026-02-09",
        "Add db.sqlite3 to .gitignore - database files should not be committed",
    ),
    ("1.03", "2026-02-09", "Updated README.md with Deployment/DB Options"),
    (
        "1.02",
        "2026-02-09",
        "Removed somre references to RCBC in places like footer, added some screenshots to the README.md added .gitkeep for the logs folder",
    ),
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
