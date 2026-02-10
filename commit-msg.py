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
Commit-msg hook to automatically increment the version number
and update the change log in project/version.py

This hook reads the commit message from the file passed as the first argument,
updates the version.py file, and stages the changes.
"""

import os
import re
import sys
import datetime
import subprocess

# Path to the version file
VERSION_FILE = "project/version.py"

def increment_version(commit_msg_file):
    """Increment the version number and update the change log."""
    # Check if the version file exists
    if not os.path.isfile(VERSION_FILE):
        print(f"Error: Version file {VERSION_FILE} not found")
        return 1

    # Read the commit message from the file passed as the first argument
    with open(commit_msg_file, 'r') as f:
        commit_msg = f.readline().strip()

    # Skip version update if commit message contains [skip version]
    if "[skip version]" in commit_msg.lower():
        print("Skipping version update as requested in commit message...")
        return 0

    # Skip version update if this is an amend commit
    # Check if HEAD exists (not the first commit) and if the commit message matches the last commit
    try:
        last_commit_msg = subprocess.check_output(['git', 'log', '-1', '--pretty=%s'], text=True).strip()
        if commit_msg == last_commit_msg:
            print("Detected amend commit. Skipping version update...")
            return 0
    except subprocess.CalledProcessError:
        # If git log fails, this might be the first commit, so continue
        pass

    # Read the version file
    with open(VERSION_FILE, 'r') as f:
        content = f.read()

    # Extract the current version
    version_match = re.search(r'VERSION = "([0-9]+\.[0-9]+)"', content)
    if not version_match:
        print(f"Error: Could not extract current version from {VERSION_FILE}")
        return 1

    current_version = version_match.group(1)

    # Split the version into major and minor parts
    major, minor = current_version.split('.')

    # Increment the minor version
    new_minor = f"{int(minor) + 1:02d}"
    new_version = f"{major}.{new_minor}"

    # Get the current date in YYYY-MM-DD format
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Update the version in the file
    new_content = re.sub(
        r'VERSION = "[0-9]+\.[0-9]+"',
        f'VERSION = "{new_version}"',
        content
    )

    # Add the new entry to the change log
    change_log_match = re.search(r'CHANGE_LOG = \[(.*?)\]', new_content, re.DOTALL)
    if change_log_match:
        change_log_content = change_log_match.group(1)
        new_entry = f'    ("{new_version}", "{current_date}", "{commit_msg}"),\n'
        new_change_log = f'CHANGE_LOG = [\n{new_entry}{change_log_content}]'
        new_content = re.sub(
            r'CHANGE_LOG = \[(.*?)\]',
            new_change_log,
            new_content,
            flags=re.DOTALL
        )

    # Write the updated content back to the file
    with open(VERSION_FILE, 'w') as f:
        f.write(new_content)

    # Stage the modified version file
    subprocess.call(['git', 'add', VERSION_FILE])

    print(f"Version incremented from {current_version} to {new_version}")
    print("The version.py file has been updated and staged.")

    return 0

def main():
    """Main function to increment version using the commit message."""
    if len(sys.argv) < 2:
        print("Error: No commit message file provided")
        return 1

    commit_msg_file = sys.argv[1]
    return increment_version(commit_msg_file)

if __name__ == "__main__":
    sys.exit(main())
