#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# build_admin_mac.sh
# Build the IR Attendance Admin Panel as a macOS .app bundle
# Run this script ON YOUR MAC (not on Windows)
# ──────────────────────────────────────────────────────────────────────────────

set -e

echo "📦 IR Attendance Admin Panel — macOS Build"
echo "============================================"

# 1. Check Python 3
if command -v /opt/homebrew/bin/python3.10 &>/dev/null; then
    PYTHON=/opt/homebrew/bin/python3.10
elif command -v python3 &>/dev/null; then
    PYTHON=python3
else
    echo "❌ Python 3 not found. Install from https://www.python.org/"
    exit 1
fi
echo "✅ Python: $($PYTHON --version)"

# 2. Create/activate virtual environment
if [ ! -d ".venv_mac" ]; then
    echo "📁 Creating virtual environment..."
    $PYTHON -m venv .venv_mac
fi
source .venv_mac/bin/activate
echo "✅ Virtual environment activated"

# 3. Install dependencies (admin-only subset — no pywin32, no pyautogui, etc.)
echo "📥 Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet \
    "urllib3<2" \
    pyinstaller \
    Pillow \
    requests \
    cryptography \
    openpyxl \
    tkcalendar \
    google-api-python-client \
    google-auth-httplib2 \
    google-auth-oauthlib

echo "✅ Dependencies installed"

# 4. Run PyInstaller
echo "🔨 Building .app bundle..."
pyinstaller -y \
    --name "IR Admin Panel" \
    --windowed \
    --onedir \
    --add-data "Admin Icon.png:." \
    --hidden-import "googleapiclient" \
    --hidden-import "google.auth" \
    --hidden-import "google_auth_oauthlib" \
    --hidden-import "tkcalendar" \
    --hidden-import "openpyxl" \
    --hidden-import "babel.numbers" \
    src/admin_panel.py

# 5. Fix permissions and remove quarantine attribute
echo "🔧 Fixing app bundle permissions..."
if [ -d "dist/IR Admin Panel.app" ]; then
    xattr -cr "dist/IR Admin Panel.app" || true
fi

echo ""
echo "✅ Build complete!"
echo "📂 Output: dist/IR Admin Panel.app"
echo ""
echo "To run: open 'dist/IR Admin Panel.app'"
echo "Or drag it to your Applications folder."
