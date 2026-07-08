#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# build_admin_app_mac.sh
# Build the IR Attendance Admin Utility as a macOS .app bundle
# Run this script on your Mac
# ──────────────────────────────────────────────────────────────────────────────

set -e

echo "📦 IR Attendance Admin Utility — macOS App Builder"
echo "=================================================="

# 1. Check Python 3
if command -v /opt/homebrew/bin/python3.10 &>/dev/null; then
    PYTHON=/opt/homebrew/bin/python3.10
elif command -v python3 &>/dev/null; then
    PYTHON=python3
else
    echo "❌ Python 3 not found."
    exit 1
fi
echo "✅ Python: $($PYTHON --version)"

# 2. Check virtual environment
if [ ! -d ".venv_mac" ]; then
    echo "📁 Creating virtual environment..."
    $PYTHON -m venv .venv_mac
fi
source .venv_mac/bin/activate
echo "✅ Virtual environment activated"

# 3. Ensure PyInstaller is installed in the virtual environment
pip install --quiet --upgrade pip
pip install --quiet pyinstaller

# 4. Run PyInstaller to build the App Bundle
echo "🔨 Building standalone macOS App bundle..."
pyinstaller -y \
    --name "IR Admin Utility" \
    --windowed \
    --onedir \
    --add-data "Icon.png:." \
    --hidden-import "PIL" \
    --hidden-import "PIL.Image" \
    --hidden-import "PIL.ImageTk" \
    --hidden-import "PIL.ImageEnhance" \
    --hidden-import "cv2" \
    --hidden-import "numpy" \
    --hidden-import "fitz" \
    --hidden-import "pytesseract" \
    --hidden-import "openpyxl" \
    --hidden-import "tkcalendar" \
    --hidden-import "babel.numbers" \
    --hidden-import "keyboard" \
    --hidden-import "pyperclip" \
    src/admin_main.py

# 5. Fix bundle permissions and clear macOS quarantine attribute
echo "🔧 Fixing app bundle permissions..."
if [ -d "dist/IR Admin Utility.app" ]; then
    xattr -cr "dist/IR Admin Utility.app" || true
fi

echo ""
echo "✅ Build complete!"
echo "📂 Output app: dist/IR Admin Utility.app"
echo ""
echo "To run the app: open 'dist/IR Admin Utility.app'"
echo "You can drag and drop it into your Applications folder!"
