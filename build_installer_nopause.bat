@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   IR Attendance - Full Build + Installer Script
echo ============================================================
echo.

REM ── Step 1: Activate venv ───────────────────────────────────
if not exist ".venv" (
    echo [1/5] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/5] Virtual environment found.
)
call .venv\Scripts\activate.bat

REM ── Step 2: Install deps ────────────────────────────────────
echo.
echo [2/5] Installing / updating Python dependencies...
pip install --upgrade pip --quiet
pip install -r Requirements.txt --quiet
pip install pyinstaller --quiet
echo     Done.

REM ── Step 3: Clean old build ─────────────────────────────────
echo.
echo [3/5] Cleaning old build outputs...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
echo     Done.

REM ── Step 4: Build with PyInstaller ──────────────────────────
echo.
echo [4/5] Building application with PyInstaller (this may take a few minutes)...
pyinstaller IR_Attendance.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build FAILED. Check output above.
    pause
    exit /b 1
)
echo     Build complete: dist\IR_Attendance\

REM ── Step 5: Compile Installer with Inno Setup ───────────────
echo.
echo [5/5] Building installer with Inno Setup...

REM Check common Inno Setup paths
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 5\ISCC.exe"

if "!ISCC!"=="" (
    echo.
    echo [WARNING] Inno Setup not found!
    echo Please install it from: https://jrsoftware.org/isdl.php
    echo Then re-run this script to create the installer.
    echo.
    echo Your built application is at: dist\IR_Attendance\
    echo You can still distribute that folder manually.
    pause
    exit /b 0
)

if not exist "installer_output" mkdir installer_output

%ISCC% IR_Attendance_Setup.iss
if errorlevel 1 (
    echo.
    echo [ERROR] Inno Setup compilation FAILED. Check output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS!
echo   Installer: installer_output\IR_Attendance_Setup.exe
echo ============================================================
echo.
echo This installer includes:
echo   - IR Attendance application
echo   - All Python dependencies (Pillow, Flask, OpenCV, etc.)
echo   - Tesseract-OCR (bundled, no separate install needed)
echo   - Desktop + Start Menu shortcuts
echo.

