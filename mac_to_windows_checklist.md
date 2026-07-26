# Mac to Windows Build Checklist

This checklist ensures that when developing on a Mac, the final `.exe` and `.apk` builds for Windows and Android remain stable and do not break due to OS-specific differences.

## 1. UI & Styling (Tkinter)
- [ ] **No Mac-Specific Libraries:** Ensure `tkmacosx` is NOT used in the final push, or is safely wrapped in a `try/except` with a `platform.system() == 'Darwin'` check.
- [ ] **Windows Color Scheme:** Ensure the original Windows color scheme is retained. Do not push Apple/Mac specific colors that ruin the established Windows UI.
- [ ] **Feature Retention:** When reverting Mac UI changes, verify that newly added features (e.g., "Import Batch", "Mobile Attendance", "Eye Logic") are NOT accidentally deleted.

## 2. File Paths & Drives
- [ ] **C: Drive Pathing:** Ensure `config.py` correctly uses `C:/IR Attendance` for `win32` systems. Mac local paths must be strictly isolated using `sys.platform`.

## 3. Keyboard Macros & Shortcuts
- [ ] **Alt+Tab vs Command+Tab:** Windows uses `Alt+Tab` for switching apps, Mac uses `Command+Tab`. Ensure `keyboard.press()` logic dynamically checks the OS (e.g., `ALT_KEY = 'command' if platform.system() == 'Darwin' else 'alt'`).
- [ ] **Global Hotkeys:** The `keyboard` module requires `sudo` on Mac and will crash. Ensure local Tkinter fallback bindings (`<Key-a>`, `<Right>`, etc.) are active for Mac development, but keep the global hotkeys intact for Windows background execution.

## 4. Mobile App (Expo / React Native)
- [ ] **App Icon:** Verify that `assets/icon.png` is properly placed in the mobile app directory so the final APK has the correct IR Attendance icon.
- [ ] **Expo Prebuild:** If the mobile app is an Expo project (`mobile_mirror`), ensure the GitHub Actions workflow includes `npx expo prebuild --platform android` before running `./gradlew assembleRelease`.

## 5. Pre-Push Verification
- [ ] **Syntax Check:** Run a quick `python3 -m py_compile src/*.py` to ensure no indentation or syntax errors were introduced during patching.
