@echo off
echo ===================================================
echo   MASTER APK BUILDER - FULL AUTOMATION
echo ===================================================
echo.

set JAVA_HOME=C:\Java
set ANDROID_HOME=C:\Android
set PATH=C:\Java\bin;C:\Android\cmdline-tools\latest\bin;C:\Android\platform-tools;%PATH%

echo [1/2] Checking for Java...
java -version
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Java 17 not active in this session.
    exit /b
)

echo [2/2] Starting Build Process...
cd mobile_admin\android

echo Cleaning...
call gradlew.bat clean

echo Building Release APK...
call gradlew.bat assembleRelease

if %ERRORLEVEL% eq 0 (
    echo SUCCESS!
) else (
    echo BUILD FAILED.
)
pause
