@echo off
echo ========================================
echo IR Attendance - Build Script
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building executable...
pyinstaller IR_Attendance.spec

echo.
echo ========================================
echo Build complete!
echo Executable location: dist\IR_Attendance.exe
echo ========================================
pause
