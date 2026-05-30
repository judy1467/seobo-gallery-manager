@echo off
chcp 65001 >nul
title Servo Gallery Manager - Windows Build
cls

echo ===========================================
echo Seobo Gallery Manager - Windows Build
echo ===========================================
echo.

rem Detect Python
set PYTHON_CMD=
where python >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :found_python
)
where py >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :found_python
)
echo ERROR: Python not found. Install from https://python.org
echo Make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:found_python
echo Using: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

rem Step 1: Create virtual environment
echo [1/4] Creating virtual environment...
if not exist venv\Scripts\python.exe (
    %PYTHON_CMD% -m venv venv
)
echo.

rem Step 2: Install dependencies
echo [2/4] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install PySide6 paramiko Pillow pyinstaller
echo.

rem Step 3: Build executable
echo [3/4] Building executable...
pyinstaller --clean build_windows.spec
echo.

rem Step 4: Verify
echo [4/4] Verifying build...
if exist dist\SeoboGalleryManager\SeoboGalleryManager.exe (
    echo.
    echo ===========================================
    echo BUILD SUCCESS
    echo Output: dist\SeoboGalleryManager\
    echo ===========================================
    echo.
    echo Deployment:
    echo   1. Zip the entire dist\SeoboGalleryManager\ folder
    echo   2. User extracts and double-clicks SeoboGalleryManager.exe
    echo   3. Settings (settings.json) appear next to the .exe
) else (
    echo.
    echo ===========================================
    echo BUILD FAILED - check errors above
    echo ===========================================
)

echo.
pause
