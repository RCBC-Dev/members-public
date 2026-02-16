@echo off
REM Run pytest with coverage and generate coverage.xml for SonarQube
REM Usage: testcoverage.bat [optional pytest args, e.g. tests/test_views.py]

REM Use venv Python if available, otherwise fall back to system Python
if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else (
    set PYTHON=python
)

set DJANGO_SETTINGS_MODULE=project.settings.development

echo.
echo === Running tests with coverage ===
echo.

%PYTHON% -m pytest -v --cov=. --cov-report=xml:coverage.xml %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo Tests failed.
    exit /b %ERRORLEVEL%
)

echo.
echo === Coverage report written to coverage.xml ===
echo Run 'python .\sonar_scan.py' to upload results to SonarQube.
echo.

exit /b 0
