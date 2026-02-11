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
Script to update the version number and add a change log entry.
Usage: python update_version.py "Description of changes"
"""

import sys
import re
import datetime
from pathlib import Path


def update_version(description):
    """
    Update the version number and add a change log entry.
    """
    version_file = Path("project/version.py")

    if not version_file.exists():
        print(f"Error: Version file not found at {version_file}")
        return False

    # Read the current version file
    content = version_file.read_text()

    # Extract the current version
    version_match = re.search(r'VERSION = ["\']([0-9.]+)["\']', content)
    if not version_match:
        print("Error: Could not find VERSION in version.py")
        return False

    current_version = version_match.group(1)

    # Increment the minor version
    major, minor = current_version.split(".")
    new_minor = int(minor) + 1
    new_version = f"{major}.{new_minor:02d}"

    # Update the version number
    content = content.replace(
        f'VERSION = "{current_version}"', f'VERSION = "{new_version}"'
    )

    # Add a new change log entry
    today = datetime.date.today().strftime("%Y-%m-%d")
    new_entry = f'    ("{new_version}", "{today}", "{description}"),'

    # Find the change log list and add the new entry at the beginning
    change_log_match = re.search(r"CHANGE_LOG = \[(.*?)\]", content, re.DOTALL)
    if not change_log_match:
        print("Error: Could not find CHANGE_LOG in version.py")
        return False

    change_log = change_log_match.group(1).strip()
    new_change_log = (
        f'\n    ("{new_version}", "{today}", "{description}"),\n{change_log}'
    )
    content = content.replace(change_log_match.group(1), new_change_log)

    # Write the updated content back to the file
    version_file.write_text(content)

    print(f"Version updated from {current_version} to {new_version}")
    print(f"Change log entry added: {description}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python update_version.py "Description of changes"')
        sys.exit(1)

    description = sys.argv[1]
    if not update_version(description):
        sys.exit(1)
