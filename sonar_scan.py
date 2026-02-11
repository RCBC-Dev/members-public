#!/usr/bin/env python
"""
SonarQube Scanner Script

This script triggers a SonarQube analysis using configuration from sonar-project.properties.
It uses the pysonar_scanner module to perform the scan.

Usage:
    python sonar_scan.py

Requirements:
    - pysonar package installed (pip install pysonar)
    - SonarQube server running at configured host
    - Valid sonar-project.properties file with project configuration
    - SONARQUBE_TOKEN environment variable or token in sonar-project.properties

The script will:
1. Read configuration from sonar-project.properties
2. Run the SonarQube scanner
3. Analyze Python, JavaScript, HTML, and CSS files
4. Upload results to the SonarQube server
5. Display the dashboard URL when complete
"""

import sys
import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import version from project
sys.path.insert(0, str(Path(__file__).parent))
from project.version import get_version


def parse_properties_file(filepath):
    """
    Parse sonar-project.properties file and return a dictionary of properties.

    Args:
        filepath: Path to sonar-project.properties

    Returns:
        dict: Dictionary of property key-value pairs
    """
    properties = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Skip lines with backslash (continuation)
                if line.endswith('\\'):
                    continue
                # Parse key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    properties[key.strip()] = value.strip()
    except Exception as e:
        print(f"ERROR: Failed to parse sonar-project.properties: {e}")
        return {}

    return properties


def run_sonar_scan():
    """
    Execute SonarQube scan using pysonar_scanner.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # Check if sonar-project.properties exists
    properties_file = Path("sonar-project.properties")
    if not properties_file.exists():
        print("ERROR: sonar-project.properties not found!")
        print("Please create sonar-project.properties with your SonarQube project configuration.")
        return 1

    # Parse properties file
    properties = parse_properties_file(properties_file)

    if not properties:
        print("ERROR: Could not parse sonar-project.properties")
        return 1

    # Get configuration from properties file
    project_key = properties.get('sonar.projectKey')
    project_name = properties.get('sonar.projectName', project_key)
    sonar_host = properties.get('sonar.host.url', 'http://localhost:9000')

    if not project_key:
        print("ERROR: sonar.projectKey not found in sonar-project.properties")
        return 1

    print("=" * 80)
    print(f"Starting SonarQube Analysis for {project_name}")
    print("=" * 80)
    print()

    # Get SonarQube token from environment variable or properties file
    sonar_token = os.environ.get("SONARQUBE_TOKEN") or properties.get('sonar.token')

    if not sonar_token:
        print("ERROR: SONARQUBE_TOKEN environment variable or sonar.token in properties not set!")
        print("Please set SONARQUBE_TOKEN in .env or add sonar.token to sonar-project.properties")
        return 1

    # Configure environment to prevent JGit from using network drive H:\
    # This fixes "Creating lock file H:\.config\jgit\config.lock failed" errors
    env = os.environ.copy()

    # Set HOME to local C: drive instead of network drive H:
    local_home = str(Path.home())
    env["HOME"] = local_home
    env["USERPROFILE"] = local_home

    # Force Git config to use local directory
    git_config_local = str(Path(local_home) / ".gitconfig")
    env["GIT_CONFIG_GLOBAL"] = git_config_local
    env["GIT_CONFIG_SYSTEM"] = git_config_local

    # Java system property for user.home
    env["_JAVA_OPTIONS"] = f"-Duser.home={local_home}"

    # Get version from project
    project_version = get_version()

    # Build the command to run pysonar_scanner
    # We use the Python module approach that worked successfully
    command = [
        sys.executable,  # Use the current Python interpreter
        "-c",
        "from pysonar_scanner import __main__; __main__.main()",
        f"--sonar-host-url={sonar_host}",
        f"--sonar-token={sonar_token}",
        f"--sonar-project-key={project_key}",
        f"--sonar-project-version={project_version}",
    ]

    print("Running SonarQube scanner...")
    print(f"Project Key: {project_key}")
    print(f"Host: {sonar_host}")
    print(f"Command: {' '.join(command[:3])} [with authentication]")
    print()

    try:
        # Run the scanner and capture output
        result = subprocess.run(
            command,
            cwd=Path.cwd(),
            capture_output=False,  # Show output in real-time
            text=True,
            env=env,  # Pass our configured environment
        )

        print()
        print("=" * 80)
        if result.returncode == 0:
            print("✓ SonarQube Analysis Completed Successfully!")
            print()
            print(f"View results at: {sonar_host}/dashboard?id={project_key}")
        else:
            print("✗ SonarQube Analysis Failed!")
            print(f"Exit code: {result.returncode}")
        print("=" * 80)

        return result.returncode

    except FileNotFoundError:
        print("ERROR: Python interpreter not found!")
        print("Please ensure Python is installed and in your PATH.")
        return 1
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        return 1


def check_prerequisites():
    """
    Check if all prerequisites are met before running the scan.

    Returns:
        bool: True if all prerequisites are met, False otherwise
    """
    print("Checking prerequisites...")
    print()

    # Check if pysonar is installed
    try:
        import pysonar_scanner  # noqa: F401

        print("✓ pysonar_scanner module found")
    except ImportError:
        print("✗ pysonar_scanner module not found!")
        print("  Install it with: pip install pysonar")
        return False

    # Check if SonarQube server is accessible
    try:
        import requests

        response = requests.get("http://localhost:9000/api/system/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print(
                f"✓ SonarQube server is UP (version {status.get('version', 'unknown')})"
            )
        else:
            print("✗ SonarQube server returned unexpected status")
            return False
    except ImportError:
        print("⚠ requests module not found - skipping server check")
        print("  Install it with: pip install requests")
    except Exception as e:
        print(f"✗ Cannot connect to SonarQube server: {e}")
        print("  Make sure SonarQube is running at http://localhost:9000")
        return False

    print()
    return True


def main():
    """
    Main entry point for the script.
    """
    print()

    # Check prerequisites
    if not check_prerequisites():
        print()
        print("Prerequisites not met. Please fix the issues above and try again.")
        return 1

    # Run the scan
    exit_code = run_sonar_scan()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
