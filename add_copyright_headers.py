#!/usr/bin/env python
"""
Add AGPL 3.0 copyright headers to source files.
Skips files that already have the copyright header to avoid duplicates.
"""

import os
import re
from pathlib import Path

# Copyright header for Python files
PYTHON_HEADER = '''# Copyright (C) 2026 Redcar & Cleveland Borough Council
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
'''

# Copyright header for JavaScript files
JS_HEADER = '''/*
 * Copyright (C) 2026 Redcar & Cleveland Borough Council
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
'''

# Copyright header for HTML and CSS files
HTML_CSS_HEADER = '''<!--
  Copyright (C) 2026 Redcar & Cleveland Borough Council
  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published by
  the Free Software Foundation, version 3.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
-->
'''

# Directories to exclude
EXCLUDE_DIRS = {
    'venv', '.venv', 'env',
    'node_modules',
    '__pycache__',
    '.git', '.pytest_cache',
    'migrations',
    'vendor',  # Third-party JavaScript libraries
}

# Files that typically shouldn't have headers
EXCLUDE_FILES = {
    'manage.py',
    'setup.py',
    '__init__.py',
    'add_copyright_headers.py',  # This script itself
}


def should_exclude_path(path):
    """Check if a path should be excluded."""
    parts = path.parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def has_copyright_header(content):
    """Check if file already has a copyright header."""
    return 'Copyright (C) 2026 Redcar & Cleveland Borough Council' in content


def add_header_to_file(file_path, header):
    """Add copyright header to a file if it doesn't already have one."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Skip if already has header
        if has_copyright_header(content):
            print(f"[SKIP] {file_path} (already has header)")
            return False

        # Add header
        new_content = header + '\n' + content

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"[OK]   {file_path}")
        return True

    except Exception as e:
        print(f"[ERR]  {file_path}: {e}")
        return False


def process_files():
    """Find and process all source files."""
    python_files = []
    js_files = []
    html_files = []
    css_files = []

    # Collect files
    for root, dirs, files in os.walk('.'):
        # Remove excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        root_path = Path(root)

        # Skip excluded paths
        if should_exclude_path(root_path):
            continue

        for file in files:
            if file in EXCLUDE_FILES:
                continue

            file_path = root_path / file

            if file.endswith('.py'):
                python_files.append(file_path)
            elif file.endswith('.js'):
                js_files.append(file_path)
            elif file.endswith('.html'):
                html_files.append(file_path)
            elif file.endswith('.css'):
                css_files.append(file_path)

    # Process files
    total = 0
    added = 0

    print("\n" + "=" * 60)
    print("Python Files (.py)")
    print("=" * 60)
    for file_path in sorted(python_files):
        total += 1
        if add_header_to_file(file_path, PYTHON_HEADER):
            added += 1

    print("\n" + "=" * 60)
    print("JavaScript Files (.js)")
    print("=" * 60)
    for file_path in sorted(js_files):
        total += 1
        if add_header_to_file(file_path, JS_HEADER):
            added += 1

    print("\n" + "=" * 60)
    print("HTML Templates (.html)")
    print("=" * 60)
    for file_path in sorted(html_files):
        total += 1
        if add_header_to_file(file_path, HTML_CSS_HEADER):
            added += 1

    print("\n" + "=" * 60)
    print("CSS Files (.css)")
    print("=" * 60)
    for file_path in sorted(css_files):
        total += 1
        if add_header_to_file(file_path, HTML_CSS_HEADER):
            added += 1

    print("\n" + "=" * 60)
    print(f"Summary: {added} files updated, {total - added} skipped")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    process_files()
