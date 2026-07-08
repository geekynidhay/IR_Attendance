@echo off
echo ===================================================
echo   Minimal Android SDK Setup for Low-Spec PCs
echo ===================================================
echo.

set JAVA_PATH=C:\Java
set SDK_PATH=C:\Android

if not exist "%%JAVA_PATH%%" (
    echo [ERROR] Please extract JDK to %%JAVA_PATH%% first.
    pause
    exit /b
)

if not exist "%%SDK_PATH%%\cmdline-tools\latest" (
    echo [ERROR] Please extract Android tools to %%SDK_PATH%%\cmdline-tools\latest.
    pause
    exit /b
)

echo [1/2] Setting environment variables...
setx JAVA_HOME "%%JAVA_PATH%%"
setx ANDROID_HOME "%%SDK_PATH%%"
setx PATH "%%PATH%%;%%JAVA_PATH%%\bin;%%SDK_PATH%%\cmdline-tools\latest\bin;%%SDK_PATH%%\platform-tools" /M

echo [2/2] Accepting Licenses...
echo y | "%%SDK_PATH%%\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root="%%SDK_PATH%%" "platform-tools" "platforms;android-34" "build-tools;34.0.0"

echo.
echo ===================================================
echo SETUP COMPLETE! You can now run build_apk.bat
echo ===================================================
pause
