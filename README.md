# IR Attendance Software

A dual-purpose desktop application for processing and viewing scanned attendance images.

## Features

### 🖼️ Image Splitter Mode
- Split scanned images vertically with visual configuration
- Drag-and-drop interface for split line and crop area
- Batch process hundreds of images automatically
- Organized output by attendance ID

### 👁️ Image Viewer Mode
- Navigate folders and images with keyboard shortcuts
- Adjust brightness (0-200%) and zoom (10-500%)
- Settings saved per subfolder
- Copy subfolder names to clipboard
- Global hotkey (Ctrl+Space) to restore focus

## Quick Start

### Running the Application

**Option 1: Run the Executable (Recommended)**
1. Navigate to the `dist` folder
2. Double-click `IR_Attendance.exe`
3. No installation required!

**Option 2: Run from Source**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Building the Executable

```bash
# Windows
build.bat

# Or manually
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller IR_Attendance.spec
```

## Usage

### Image Splitter Mode
1. Click "Image Splitter Mode" from the main menu
2. Browse and select a sample image
3. Drag the red line to set split position
4. (Optional) Enable crop and drag green rectangle corners
5. Select Raw Data folder and output folder
6. Click "Process All Images"

### Image Viewer Mode
1. Click "Image Viewer Mode" from the main menu
2. Browse and select your batch folder
3. Click "Load"
4. Navigate using arrow keys:
   - **↓** Next subfolder
   - **↑** Previous subfolder
   - **→** Next image
   - **←** Previous image
5. Adjust brightness and zoom as needed
6. Click "Copy Subfolder Name" when needed
7. Press **Ctrl+Space** from any app to return to focus

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| ↓ | Next subfolder |
| ↑ | Previous subfolder |
| → | Next image |
| ← | Previous image |
| Ctrl+Space | Bring window to focus (works from any application) |

## Requirements

- Windows 7 or later
- Python 3.10+ (only for running from source)

## Documentation

- [USER_GUIDE.md](USER_GUIDE.md) - Complete user manual with detailed instructions
- See the `dist` folder for the standalone executable

## Technical Details

**Built with:**
- Python 3.13
- Tkinter (GUI)
- Pillow (Image processing)
- pywin32 (Window management)
- keyboard (Global hotkeys)
- PyInstaller (Executable building)

**File Structure:**
```
PC-IR-ATT/
├── main.py                    # Main entry point
├── config.py                  # Settings management
├── window_manager.py          # Window focus control
├── image_processor.py         # Image processing logic
├── splitter_mode.py           # Splitter UI
├── viewer_mode.py             # Viewer UI
├── folder_navigator.py        # Folder navigation
├── image_controls.py          # Custom controls
├── requirements.txt           # Dependencies
├── IR_Attendance.spec         # Build config
├── build.bat                  # Build script
├── USER_GUIDE.md             # User documentation
└── dist/
    └── IR_Attendance.exe     # Standalone executable (18.8 MB)
```

## License

© 2026 IR Attendance. All rights reserved.

---

**Version**: 1.0  
**Build Date**: February 6, 2026
