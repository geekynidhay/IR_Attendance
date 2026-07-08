@echo off
echo ===================================================
echo   IR Attendance Mobile Admin - Local APK Builder
echo ===================================================
echo.
echo Requirements:
echo 1. Java JDK 17 (or newer)
echo 2. Android SDK
echo.
echo Checking for environment...
java -version >nul 2>&1
if %%ERRORLEVEL%% neq 0 (
    echo [ERROR] Java not found. Please install JDK 17.
    pause
    exit /b
)

echo [1/3] Navigating to mobile_admin...
cd mobile_admin

echo [2/3] Cleaning previous builds...
cd android
call gradlew clean
if %%ERRORLEVEL%% neq 0 (
    echo [ERROR] Gradle clean failed.
    pause
    exit /b
)

echo [3/3] Building Release APK...
call gradlew assembleRelease
if %%ERRORLEVEL%% neq 0 (
    echo [ERROR] APK Build failed.
    pause
    exit /b
)

echo.
echo ===================================================
echo SUCCESS! Your APK is ready at:
echo mobile_admin\android\app\build\outputs\apk\release\app-release.apk
echo ===================================================
pause
