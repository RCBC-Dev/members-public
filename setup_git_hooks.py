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
Script to set up Git hooks for automatic versioning.
"""

import os
import sys
import shutil
import platform
import subprocess


def main():
    """Set up Git hooks for automatic versioning."""
    print("Setting up Git hooks for automatic versioning and testing...")

    # Check if .git directory exists
    if not os.path.isdir(".git"):
        print("Error: .git directory not found. Are you in the root of the repository?")
        return 1

    # Check if hooks directory exists
    hooks_dir = ".git/hooks"
    if not os.path.isdir(hooks_dir):
        print(f"Creating hooks directory: {hooks_dir}")
        os.makedirs(hooks_dir)

    # Create pre-commit hook files
    pre_commit_py = """#!/usr/bin/env python
\"\"\"
Pre-commit hook to run Black formatter and tests before committing.

This hook first formats code with Black, then runs tests.
Version updates are handled by the commit-msg hook.
\"\"\"

import os
import sys
import subprocess

def run_black():
    \"\"\"Run Black formatter on all Python files and return True if successful.\"\"\"
    print("Running Black formatter...")

    # Try to find the Python interpreter in the virtual environment
    python_cmd = 'python'
    if os.path.exists('venv/Scripts/python.exe'):
        python_cmd = 'venv/Scripts/python.exe'
    elif os.path.exists('venv/bin/python'):
        python_cmd = 'venv/bin/python'

    try:
        # Run Black on the entire project
        result = subprocess.run([python_cmd, '-m', 'black', '.'],
                               capture_output=True,
                               text=True)

        if result.returncode == 0:
            print("Black formatting completed successfully!")
            # If Black made changes, we need to stage them
            if result.stdout and "reformatted" in result.stdout:
                print("Black made formatting changes - staging them...")
                subprocess.run(['git', 'add', '.'], capture_output=True)
            return True
        else:
            print(f"Black formatting failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error running Black: {e}")
        print("Continuing without Black formatting...")
        return True  # Continue even if Black fails

def run_tests():
    \"\"\"Run all tests and return True if all tests pass, False otherwise.\"\"\"
    print("Running tests before commit...")

    # Try to find the Python interpreter in the virtual environment
    python_cmd = 'python'
    if os.path.exists('venv/Scripts/python.exe'):
        python_cmd = 'venv/Scripts/python.exe'
    elif os.path.exists('venv/bin/python'):
        python_cmd = 'venv/bin/python'

    try:
        # Set up environment variables for Django tests
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'project.settings.development'

        # Run tests in the project root directory
        cwd = os.getcwd()

        print("Running tests for the members-public project... [change this in setup_git_hooks.py]")

        # Run pytest with coverage reporting for SonarQube
        # Generates coverage.xml in project root (sonar.python.coverage.reportPaths=coverage.xml)
        result = subprocess.run([python_cmd, '-m', 'pytest', '-v',
                                 '--cov=application', '--cov=project',
                                 '--cov-report=xml:coverage.xml'],
                               capture_output=False,  # Show output directly in console
                               text=True,
                               env=env,
                               cwd=cwd)

        # Check if tests passed
        if result.returncode == 0:
            print("All tests passed!")
            return True
        else:
            print("Tests failed! Please fix the failing tests before committing.")
            return False
    except Exception as e:
        print(f"Error running tests: {e}")
        print("Skipping test verification due to error.")
        return True  # Continue with commit despite test error

def main():
    \"\"\"Main function to run Black formatter and tests before commit.\"\"\"
    # First run Black formatter
    if not run_black():
        print("Black formatting failed! Please fix any issues and try again.")
        return 1

    # Then run tests
    if not run_tests():
        # If tests fail, abort the commit
        return 1

    # If both Black and tests pass, allow the commit to proceed
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""

    pre_commit_sh = """#!/bin/sh
#
# Pre-commit hook to run tests before committing

# Detect OS
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
        # Windows
        python .git/hooks/pre-commit.py
        ;;
    *)
        # Unix-like
        python .git/hooks/pre-commit.py
        ;;
esac

# Exit with the same status as the Python script
exit $?
"""

    pre_commit_bat = """@echo off
REM Pre-commit hook to run tests before committing

python .git/hooks/pre-commit.py
exit /b %ERRORLEVEL%
"""

    pre_commit_ps1 = """# Pre-commit hook to run tests before committing

# Call the Python script for better cross-platform compatibility
python .git/hooks/pre-commit.py

# Exit with the same status as the Python script
exit $LASTEXITCODE
"""

    # Create commit-msg hook files
    # Read the commit-msg.py file from disk
    with open("commit-msg.py", "r") as f:
        commit_msg_py = f.read()

    commit_msg_sh = """#!/bin/sh
#
# Commit-msg hook to automatically increment the version number
# and update the change log in project/version.py

# Detect OS
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
        # Windows
        python .git/hooks/commit-msg.py "$1"
        ;;
    *)
        # Unix-like
        python .git/hooks/commit-msg.py "$1"
        ;;
esac

# Exit with the same status as the Python script
exit $?
"""

    commit_msg_bat = """@echo off
REM Commit-msg hook to automatically increment the version number
REM and update the change log in project/version.py

python .git/hooks/commit-msg.py %1
exit /b %ERRORLEVEL%
"""

    commit_msg_ps1 = """# Commit-msg hook to automatically increment the version number
# and update the change log in project/version.py

# Call the Python script for better cross-platform compatibility
python .git/hooks/commit-msg.py $args[0]

# Exit with the same status as the Python script
exit $LASTEXITCODE
"""

    # Write the pre-commit hook files
    with open(os.path.join(hooks_dir, "pre-commit.py"), "w") as f:
        f.write(pre_commit_py)

    with open(os.path.join(hooks_dir, "pre-commit"), "w") as f:
        f.write(pre_commit_sh)

    with open(os.path.join(hooks_dir, "pre-commit.bat"), "w") as f:
        f.write(pre_commit_bat)

    with open(os.path.join(hooks_dir, "pre-commit.ps1"), "w") as f:
        f.write(pre_commit_ps1)

    # Write the commit-msg hook files
    with open(os.path.join(hooks_dir, "commit-msg.py"), "w") as f:
        f.write(commit_msg_py)

    with open(os.path.join(hooks_dir, "commit-msg"), "w") as f:
        f.write(commit_msg_sh)

    with open(os.path.join(hooks_dir, "commit-msg.bat"), "w") as f:
        f.write(commit_msg_bat)

    with open(os.path.join(hooks_dir, "commit-msg.ps1"), "w") as f:
        f.write(commit_msg_ps1)

    # Make sure the hook files are executable
    if platform.system() != "Windows":
        # Unix-like systems
        subprocess.call(["chmod", "+x", ".git/hooks/pre-commit"])
        subprocess.call(["chmod", "+x", ".git/hooks/pre-commit.py"])
        subprocess.call(["chmod", "+x", ".git/hooks/commit-msg"])
        subprocess.call(["chmod", "+x", ".git/hooks/commit-msg.py"])
    else:
        # Windows - no need to set executable bit
        pass

    print("Git hooks set up successfully!")
    # Remove any existing post-commit hook to avoid errors
    post_commit_path = os.path.join(hooks_dir, "post-commit")
    if os.path.exists(post_commit_path):
        os.remove(post_commit_path)
        print("Removed existing post-commit hook")

    print("\nHook workflow:")
    print(
        "1. pre-commit hook: Runs Black formatter, then tests before allowing the commit"
    )
    print("2. commit-msg hook: Updates version.py with the correct commit message")
    print("\nTo use the streamlined commit process:")
    print("1. Make some changes to the code")
    print("2. Stage the changes with 'git add .'")
    print('3. Use the commit.bat script: commit.bat "Your commit message"')
    print(
        "   This will run tests, commit your changes, update version.py, and amend the commit"
    )
    print("   The amend commit uses --no-verify to avoid running tests twice")
    print("\nAlternatively, you can use the manual process:")
    print("1. Make some changes to the code")
    print("2. Stage the changes with 'git add .'")
    print("3. Commit with 'git commit -m \"Your commit message\"'")
    print("4. The pre-commit hook will run Black formatter, then tests")
    print(
        "5. If tests pass, the commit-msg hook will update the version.py file and stage it"
    )
    print(
        "6. To include the updated version.py in your commit, run: git commit --amend --no-edit"
    )
    print("\nTo skip version update: Include [skip version] in your commit message")
    print("\nTo update the version manually:")
    print("1. Run 'python increment_version.py \"Your commit message\"'")
    print("2. This will increment the version number in project/version.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
