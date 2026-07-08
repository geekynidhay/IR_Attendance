# IR Attendance - User Guide

## Overview
IR Attendance is a dual-purpose application for managing and viewing scanned attendance images.

## Features

### 1. Image Splitter Mode
Split scanned images vertically with customizable crop areas.

**How to use:**
1. Click "Browse Sample Image" to select one image that represents your batch
2. Drag the **red vertical line** to set where all images will be split
3. (Optional) Enable crop and drag the corners of the **green rectangle** to set crop area
4. Browse and select your "Raw Data" folder containing all images to process
5. Browse and select an output folder where split images will be saved
6. Click "Process All Images"

**Output:**
- Images are grouped by their base name (e.g., 01805922-1, 01805922-2 → folder "01805922")
- Each image is split into two: `[original-name]-left.jpg` and `[original-name]-right.jpg`

### 2. Image Viewer Mode
Navigate through organized image folders with brightness and zoom controls.

**How to use:**
1. Click "Browse" to select your batch folder (containing subfolders with images)
2. Click "Load" to load the folder structure
3. Use keyboard navigation:
   - **↓ (Down)**: Next subfolder
   - **↑ (Up)**: Previous subfolder
   - **→ (Right)**: Next image in current subfolder
   - **← (Left)**: Previous image in current subfolder
4. Adjust brightness using the vertical slider (0-200%)
   - Use **+** and **-** buttons for 1% adjustments
5. Adjust zoom using the horizontal slider (10-500%)
   - Use **+** and **-** buttons for 1% adjustments

**Special Features:**
- Brightness and zoom settings are **saved per subfolder**
- When you return to a subfolder, your previous settings are restored
- Click "Copy Subfolder Name" to copy the current subfolder name to clipboard
- Use **Ctrl+Space** from any application to bring IR Attendance window back to focus

## Workflow Example

### Typical Use Case:
1. **Split images** in raw data using Image Splitter Mode
2. **View and process** images using Image Viewer Mode
3. Copy subfolder name and enter it into your attendance software
4. Press **Ctrl+Space** to quickly return to IR Attendance
5. Use arrow keys to navigate through images and subfolders

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| ↓ | Next subfolder |
| ↑ | Previous subfolder |
| → | Next image |
| ← | Previous image |
| Ctrl+Space | Bring window to focus (works from any application) |

## Tips

- **Brightness**: 100% is original. Lower values darken, higher values brighten
- **Zoom**: 100% is original size. Use higher values to zoom in, lower to zoom out
- **Settings Persistence**: Brightness and zoom are saved automatically for each subfolder
- **Quick Navigation**: Use keyboard arrows for fastest navigation
- **Window Focus**: Always use Ctrl+Space to return to IR Attendance after typing elsewhere

## Troubleshooting

**Images not loading?**
- Ensure images are in supported formats: JPG, JPEG, PNG, BMP, TIFF
- Check that images are in subfolders, not directly in the batch folder

**Split not working?**
- Make sure Raw Data folder path is correct
- Ensure output folder has write permissions
- Check that image names follow the pattern: base-number (e.g., 01805922-1)

**Hotkey not working?**
- Ensure the application is running
- Try clicking on the IR Attendance window first
- Check if another application is using Ctrl+Space

## System Requirements
- Windows 7 or later
- Minimum 4GB RAM
- 100MB free disk space
- Display resolution: 1024x768 or higher

---

**IR Attendance v1.0**
