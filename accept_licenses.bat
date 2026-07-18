@echo off
set JAVA_HOME=C:\Java
set PATH=C:\Java\bin;%PATH%
echo Accepting ALL Android SDK and NDK Licenses...
powershell -Command "'y' * 200 | & 'C:\Android\cmdline-tools\latest\bin\sdkmanager.bat' --licenses --sdk_root=C:\Android"
echo.
echo Attempting to install specific NDK and SDK components...
powershell -Command "'y' * 200 | & 'C:\Android\cmdline-tools\latest\bin\sdkmanager.bat' --sdk_root=C:\Android 'ndk;27.1.12297006' 'platforms;android-36' 'build-tools;36.0.0'"
echo Done.
