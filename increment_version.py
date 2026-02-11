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

#!/usr/bin/env python
"""
Script to manually increment the version number and update the change log.
"""

import os
import re
import sys
import datetime

# Path to the version file
VERSION_FILE = "project/version.py"


def increment_version(commit_msg=None):
    """Increment the version number and update the change log."""
    # Check if the version file exists
    if not os.path.isfile(VERSION_FILE):
        print(f"Error: Version file {VERSION_FILE} not found")
        return 1

    # Read the version file
    with open(VERSION_FILE, "r") as f:
        content = f.read()

    # Extract the current version
    version_match = re.search(r'VERSION = "([0-9]+\.[0-9]+)"', content)
    if not version_match:
        print(f"Error: Could not extract current version from {VERSION_FILE}")
        return 1

    current_version = version_match.group(1)

    # Split the version into major and minor parts
    major, minor = current_version.split(".")

    # Increment the minor version
    new_minor = f"{int(minor) + 1:02d}"
    new_version = f"{major}.{new_minor}"

    # Get the commit message
    if not commit_msg:
        commit_msg = input("Enter a description for this version: ")

    # Get the current date in YYYY-MM-DD format
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Update the version in the file
    new_content = re.sub(
        r'VERSION = "[0-9]+\.[0-9]+"', f'VERSION = "{new_version}"', content
    )

    # Add the new entry to the change log
    change_log_match = re.search(r"CHANGE_LOG = \[(.*?)\]", new_content, re.DOTALL)
    if change_log_match:
        change_log_content = change_log_match.group(1)
        new_entry = f'    ("{new_version}", "{current_date}", "{commit_msg}"),\n'
        new_change_log = f"CHANGE_LOG = [\n{new_entry}{change_log_content}]"
        new_content = re.sub(
            r"CHANGE_LOG = \[(.*?)\]", new_change_log, new_content, flags=re.DOTALL
        )

    # Write the updated content back to the file
    with open(VERSION_FILE, "w") as f:
        f.write(new_content)

    print(f"Version incremented from {current_version} to {new_version}")
    return 0


def main():
    """Main function."""
    # Get the commit message from command line arguments
    commit_msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    return increment_version(commit_msg)


if __name__ == "__main__":
    sys.exit(main())
