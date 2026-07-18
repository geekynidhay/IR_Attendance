@echo off
set JAVA_HOME=C:\Java
set PATH=C:\Java\bin;%PATH%
echo Setting up SDK...
(
echo y
echo y
echo y
echo y
echo y
echo y
echo y
echo y
echo y
echo y
) | C:\Android\cmdline-tools\latest\bin\sdkmanager.bat --sdk_root=C:\Android "platform-tools" "platforms;android-34" "build-tools;34.0.0"
echo Accepting licenses...
(
echo y
echo y
echo y
echo y
echo y
echo y
echo y
echo y
echo y
echo y
) | C:\Android\cmdline-tools\latest\bin\sdkmanager.bat --licenses --sdk_root=C:\Android
echo Done.
