@echo off
REM Streamlined commit script that handles both the initial commit and the amend commit
REM Usage: commit "Your commit message"

git add .

REM Check if a commit message was provided
if "%~1"=="" (
    echo Error: No commit message provided.
    echo Usage: commit "Your commit message"
    exit /b 1
)

REM Store the commit message
set COMMIT_MSG=%~1

echo.
echo === Running initial commit with message: "%COMMIT_MSG%" ===
echo.

REM Run the initial commit
git commit -m "%COMMIT_MSG%"

REM Check if the commit was successful
if %ERRORLEVEL% neq 0 (
    echo.
    echo Initial commit failed. Please fix any issues and try again.
    exit /b %ERRORLEVEL%
)

echo.
echo === Running amend commit to include updated version.py (skipping tests) ===
echo.

REM Run the amend commit with --no-verify to skip running tests again
git commit --amend --no-edit --no-verify

REM Check if the amend commit was successful
if %ERRORLEVEL% neq 0 (
    echo.
    echo Amend commit failed. Please fix any issues and try again.
    exit /b %ERRORLEVEL%
)

echo.
echo === Commit completed successfully ===
echo.

exit /b 0
