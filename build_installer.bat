@echo off
:: ============================================================
::  IR Attendance - One-Click Build Script
::  Run this to produce:  installer_output\IR_Attendance_Setup.exe
:: ============================================================
title IR Attendance - Build

echo.
echo ========================================================
echo   IR Attendance Full Build
echo ========================================================
echo.

:: ── Step 0: Install / upgrade PyInstaller ────────────────────────────────────
echo [1/5] Checking PyInstaller...
pip install --quiet --upgrade pyinstaller
if %errorlevel% neq 0 (
    echo ERROR: pip failed. Make sure Python is installed and in PATH.
    pause & exit /b 1
)

:: ── Step 1: Clean previous build ─────────────────────────────────────────────
echo [2/5] Cleaning old build artefacts...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
if exist "installer_output" rmdir /s /q "installer_output"

:: ── Step 2: Build with PyInstaller ───────────────────────────────────────────
echo [3/5] Building EXE with PyInstaller...
python -m PyInstaller --clean --noconfirm IR_Attendance.spec
:: NOTE: PyInstaller returns exit code 1 even on successful builds that have analysis
:: warnings (e.g. missing optional hidden imports). We check for the actual EXE instead.
if not exist "dist\IR_Attendance\IR_Attendance.exe" (
    echo.
    echo ERROR: PyInstaller build failed - IR_Attendance.exe not produced.
    echo Check the output above for details.
    pause & exit /b 1
)

echo.
echo [3/5] PyInstaller build complete.  Output: dist\IR_Attendance\

:: ── Step 3: Download VC++ Redist if not present ──────────────────────────────
echo [4/5] Checking for vc_redist.x64.exe...
if not exist "vc_redist.x64.exe" (
    echo     Downloading VC++ 2015-2022 Redistributable from Microsoft...
    powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile 'vc_redist.x64.exe' -UseBasicParsing"
    if %errorlevel% neq 0 (
        echo     WARNING: Could not download vc_redist.x64.exe automatically.
        echo     Please download it manually from:
        echo       https://aka.ms/vs/17/release/vc_redist.x64.exe
        echo     and place it next to this .bat file, then re-run this script.
        pause & exit /b 1
    )
    echo     Downloaded successfully.
) else (
    echo     vc_redist.x64.exe already present, skipping download.
)

:: ── Step 4: Build Inno Setup installer ───────────────────────────────────────
echo [5/5] Building installer with Inno Setup...

:: Try the standard Inno Setup installation paths
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
    echo.
    echo    Inno Setup 6 not found.
    echo    Download and install it from:  https://jrsoftware.org/isdl.php
    echo.
    echo    Once installed, re-run this script to create the installer.
    echo.
    echo    Your PyInstaller build is still available at: dist\IR_Attendance\
    echo    You can distribute that folder directly as a portable version.
    pause & exit /b 1
)

"%ISCC%" "IR_Attendance_Setup.iss"
if %errorlevel% neq 0 (
    echo ERROR: Inno Setup failed.  Check the output above for details.
    pause & exit /b 1
)

:: ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo ========================================================
echo   BUILD COMPLETE
echo ========================================================
echo.
echo   Installer:  installer_output\IR_Attendance_Setup.exe
echo.
echo   This single EXE contains:
echo     - IR Attendance application
echo     - All Python dependencies (bundled)
echo     - Tesseract OCR engine + English language data
echo     - Visual C++ 2022 Runtime
echo     - Android platform-tools (ADB + scrcpy)
echo     - Firewall rules for phone mirror
echo     - Desktop + Start Menu shortcuts
echo.
echo   Give installer_output\IR_Attendance_Setup.exe to any user.
echo   No other software needs to be installed on their PC.
echo.
pause
