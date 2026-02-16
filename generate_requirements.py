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
Generate update_requirements.txt (~=) and upgrade_requirements.txt (>=)
from requirements.txt by replacing pinned == versions.

Usage:
    python generate_requirements.py
"""

import re
import sys


def read_requirements(path):
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read().splitlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    print(f"Error: could not read {path}", file=sys.stderr)
    sys.exit(1)


def write_requirements(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def convert(lines, operator):
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            result.append(line)
            continue
        # Match package==version, handling post/pre release suffixes
        match = re.match(r"^([A-Za-z0-9_.\-]+)==(.+)$", stripped)
        if match:
            package, version = match.group(1), match.group(2)
            if operator == "~=":
                # ~= requires at least two version components.
                # Strip post/pre/dev/local suffixes to get the base version.
                base = re.sub(
                    r"\.(post|pre|dev|a|b|rc)\d*$", "", version, flags=re.IGNORECASE
                )
                result.append(f"{package}~={base}")
            else:
                result.append(f"{package}>={version}")
        else:
            result.append(line)
    return result


def main():
    source = "requirements.txt"
    lines = read_requirements(source)

    update_lines = convert(lines, "~=")
    write_requirements("update_requirements.txt", update_lines)
    print(f"Written update_requirements.txt ({len(update_lines)} packages)")

    upgrade_lines = convert(lines, ">=")
    write_requirements("upgrade_requirements.txt", upgrade_lines)
    print(f"Written upgrade_requirements.txt ({len(upgrade_lines)} packages)")


if __name__ == "__main__":
    main()
