#!/usr/bin/env python3
"""
Repo Comparison Utility Script

Compares the public repo with the private internal repo to identify:
- Files with differences (SHA256 fingerprints)
- Hardcoded domain/branding values that should be externalised to .env
- Files present in one repo but not the other

Usage:
    python compare_repos.py [--private-repo PATH]

Example:
    python compare_repos.py
    python compare_repos.py --private-repo C:/Dev/External/private/members2
"""

import argparse
import hashlib
import os
import sys
import re
from pathlib import Path
from difflib import unified_diff
from typing import Dict, List, Tuple, Set

try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


# Configuration
SKIP_DIRS = {
    "venv",
    "__pycache__",
    "migrations",
    ".git",
    "media",
    "logs",
    "staticfiles",
    "htmlcov",
    "node_modules",
    ".env",
    "db.sqlite3",
    ".env_example",
    ".claude",
}
ALLOWED_EXTENSIONS = {".py", ".html", ".js", ".css"}

# Branding detection patterns
BRANDING_PATTERNS = [
    # Domain pattern
    (r"[a-zA-Z0-9-]+\.redclev\.net", "DOMAIN"),
    (r"[a-zA-Z0-9-]+\.rcbc\.[a-z]+", "RCBC_DOMAIN"),
    (r"redclev|rcbc|redcar", "BRANDING_TERM"),
    # Settings patterns
    (
        r"(?:ALLOWED_HOSTS|CORS_ALLOWED_ORIGINS|CSRF_TRUSTED_ORIGINS)\s*=\s*\[([^\]]+)\]",
        "SETTINGS_LIST",
    ),
    (r'DATABASE_HOST\s*=\s*["\']([^"\']+)["\']', "DATABASE_HOST"),
]


def colored(text: str, color: str) -> str:
    """Apply color to text if colorama is available."""
    if not HAS_COLORAMA:
        return text
    color_map = {
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "cyan": Fore.CYAN,
        "white": Fore.WHITE,
    }
    return color_map.get(color, "") + text + Style.RESET_ALL


def get_file_extension(filepath: str) -> str:
    """Get the file extension."""
    return Path(filepath).suffix.lower()


def strip_copyright_header(content: str, filepath: str) -> str:
    """Strip AGPL copyright header from file content based on file type."""
    ext = get_file_extension(filepath)

    if ext == ".py":
        # Python: remove block of # comment lines followed by blank line
        pattern = r"^(#.*?\n)+\n"
        content = re.sub(pattern, "", content, flags=re.MULTILINE)
    elif ext == ".js":
        # JavaScript: remove /* ... */ block at start containing Copyright
        pattern = r"^/\*[\s\S]*?\*/\s*\n"
        content = re.sub(pattern, "", content)
    elif ext in {".html", ".css"}:
        # HTML/CSS: remove <!-- ... --> block at start containing Copyright
        pattern = r"^<!--[\s\S]*?-->\s*\n"
        content = re.sub(pattern, "", content)

    return content.lstrip("\n")


def compute_sha256(filepath: str, strip_headers: bool = True) -> str:
    """Compute SHA256 hash of a file, optionally stripping copyright headers."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if strip_headers:
            content = strip_copyright_header(content, filepath)

        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    except Exception as e:
        # Fallback: return error indicator
        return f"error_{hash(str(e))}"


def should_skip(path: str) -> bool:
    """Check if a path should be skipped."""
    parts = Path(path).parts
    for part in parts:
        if part in SKIP_DIRS:
            return True
    return False


def get_files(repo_path: str) -> Dict[str, str]:
    """
    Get all relevant files from a repo.

    Returns:
        Dict mapping relative paths to absolute paths
    """
    files = {}
    repo_path = Path(repo_path)

    for root, dirs, filenames in os.walk(repo_path):
        # Skip directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in filenames:
            if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            abs_path = Path(root) / filename
            rel_path = abs_path.relative_to(repo_path)

            if not should_skip(str(rel_path)):
                files[str(rel_path)] = str(abs_path)

    return files


def detect_branding(lines: List[str]) -> List[Tuple[int, str, str]]:
    """
    Detect branding/domain patterns in diff lines.

    Returns:
        List of (line_number, detected_value, suggested_var_name)
    """
    detected = []

    for line_num, line in enumerate(lines, 1):
        for pattern, pattern_type in BRANDING_PATTERNS:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                value = match.group(0)
                suggested_var = generate_env_var_name(value, pattern_type)
                detected.append((line_num, value, suggested_var))

    return detected


def generate_env_var_name(value: str, pattern_type: str) -> str:
    """Generate a suggested .env variable name from detected value."""
    if pattern_type == "DOMAIN":
        # Extract domain like "members2.redclev.net"
        domain_part = value.split(".")[0].upper()
        return f"{domain_part}_DOMAIN"
    elif pattern_type == "RCBC_DOMAIN":
        return "RCBC_DOMAIN"
    elif pattern_type == "BRANDING_TERM":
        return "BRANDING_VALUE"
    elif pattern_type == "SETTINGS_LIST":
        return "ALLOWED_HOSTS"
    elif pattern_type == "DATABASE_HOST":
        return "DATABASE_HOST"
    else:
        return "CUSTOM_VALUE"


def get_diff(
    public_file: str, private_file: str, strip_headers: bool = True
) -> List[str]:
    """Get unified diff between two files, optionally stripping copyright headers."""
    try:
        with open(public_file, "r", encoding="utf-8", errors="replace") as f:
            public_content = f.read()
    except Exception as e:
        return [f"Error reading public file: {e}"]

    try:
        with open(private_file, "r", encoding="utf-8", errors="replace") as f:
            private_content = f.read()
    except Exception as e:
        return [f"Error reading private file: {e}"]

    if strip_headers:
        public_content = strip_copyright_header(public_content, public_file)
        private_content = strip_copyright_header(private_content, private_file)

    public_lines = public_content.splitlines(keepends=True)
    private_lines = private_content.splitlines(keepends=True)

    diff = list(
        unified_diff(
            public_lines,
            private_lines,
            fromfile="public",
            tofile="private",
            lineterm="",
        )
    )

    return diff


def format_diff_output(
    diff_lines: List[str], public_file: str, private_file: str
) -> str:
    """Format diff output with coloring."""
    output = []

    # File header
    output.append(colored(f"--- {Path(public_file).name} ---", "cyan"))
    output.append(f"Public:  {public_file}")
    output.append(f"Private: {private_file}")

    # SHA256 hashes
    public_sha = compute_sha256(public_file)
    private_sha = compute_sha256(private_file)
    output.append(f"SHA256 public:  {public_sha[:16]}...")
    output.append(f"SHA256 private: {private_sha[:16]}...")
    output.append("")

    # Diff content with coloring
    for line in diff_lines:
        if line.startswith("-"):
            output.append(colored(line, "red"))
        elif line.startswith("+"):
            output.append(colored(line, "green"))
        else:
            output.append(line)

    # Branding detection
    branding_found = detect_branding(diff_lines)
    if branding_found:
        output.append("")
        output.append(colored("[BRANDING DETECTED]", "yellow"))
        seen = set()
        for line_num, value, suggested_var in branding_found:
            key = (value, suggested_var)
            if key not in seen:
                output.append(f"  {value}")
                output.append(f"  Suggested .env variable: {suggested_var}")
                seen.add(key)

    return "\n".join(output)


def compare_repos(public_path: str, private_path: str) -> None:
    """Compare two repos and print a report."""
    public_path = Path(public_path).resolve()
    private_path = Path(private_path).resolve()

    if not public_path.exists():
        print(colored(f"ERROR: Public repo not found: {public_path}", "red"))
        sys.exit(1)

    if not private_path.exists():
        print(colored(f"ERROR: Private repo not found: {private_path}", "red"))
        sys.exit(1)

    # Get all files
    public_files = get_files(str(public_path))
    private_files = get_files(str(private_path))

    # Categorize files
    public_only = set(public_files.keys()) - set(private_files.keys())
    private_only = set(private_files.keys()) - set(public_files.keys())
    common = set(public_files.keys()) & set(private_files.keys())

    # Check which common files differ
    identical = []
    different = []

    for rel_path in sorted(common):
        pub_sha = compute_sha256(public_files[rel_path])
        priv_sha = compute_sha256(private_files[rel_path])
        if pub_sha == priv_sha:
            identical.append(rel_path)
        else:
            different.append(rel_path)

    # Print header
    print()
    print(colored("=" * 60, "cyan"))
    print(colored("=== REPO COMPARISON REPORT ===", "cyan"))
    print(colored("=" * 60, "cyan"))
    print(f"Public:  {public_path}")
    print(f"Private: {private_path}")
    print()

    # Print summary
    print(colored("=== FILES COMPARED ===", "cyan"))
    print(f"Identical (SHA256 match):  {len(identical)} files")
    print(f"Different:                  {len(different)} files")
    print(f"Private-only:               {len(private_only)} files")
    print(f"Public-only:                {len(public_only)} files")
    print()

    # Print differing files with diffs
    if different:
        print(colored("=== DIFFERING FILES ===", "cyan"))
        print()

        for rel_path in sorted(different):
            public_file = public_files[rel_path]
            private_file = private_files[rel_path]

            diff_lines = get_diff(public_file, private_file)
            print(format_diff_output(diff_lines, public_file, private_file))
            print()

    # Print file lists
    if private_only:
        print(colored("=== PRIVATE-ONLY FILES ===", "cyan"))
        for rel_path in sorted(private_only):
            print(f"  {rel_path}")
        print()

    if public_only:
        print(colored("=== PUBLIC-ONLY FILES ===", "cyan"))
        for rel_path in sorted(public_only):
            print(f"  {rel_path}")
        print()

    # Print suggested .env additions
    all_branding = set()
    for rel_path in different:
        public_file = public_files[rel_path]
        private_file = private_files[rel_path]
        diff_lines = get_diff(public_file, private_file)
        branding_found = detect_branding(diff_lines)
        for line_num, value, suggested_var in branding_found:
            all_branding.add((value, suggested_var))

    if all_branding:
        print(colored("=== SUGGESTED .env_example ADDITIONS ===", "cyan"))
        for value, suggested_var in sorted(all_branding, key=lambda x: x[1]):
            example_value = f'your-{suggested_var.lower().replace("_", "-")}.org'
            print(f"{suggested_var}={example_value}")
        print()

    print(colored("=" * 60, "cyan"))
    print(colored("Report complete.", "cyan"))
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare public and private repos to identify differences and branding."
    )
    parser.add_argument(
        "--private-repo",
        default="../private/members2",
        help="Path to private repo (default: ../private/members2)",
    )

    args = parser.parse_args()

    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    public_path = script_dir
    private_path = script_dir / args.private_repo

    compare_repos(str(public_path), str(private_path))


if __name__ == "__main__":
    main()
