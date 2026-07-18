; ============================================================
;  IR Attendance - Inno Setup 6 Installer Script
;  Produces a single self-contained IR_Attendance_Setup.exe
;  Bundles: IR Attendance app + Tesseract-OCR + VC++ Runtime
; ============================================================

#define MyAppName      "IR Attendance"
#define MyAppVersion   "2.1"
#define MyAppPublisher "IR Attendance"
#define MyAppExeName   "IR_Attendance.exe"
#define MyAppDir       "dist\IR_Attendance"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=IR_Attendance_Setup
SetupIconFile=app.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=no
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
MinVersion=10.0
; Allow user to choose whether to create shortcuts
AlwaysShowComponentsList=yes

; ── Splash / wizard image ──────────────────────────────────
; WizardImageFile=installer_banner.bmp

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── Optional components ───────────────────────────────────────────────────────
[Components]
Name: "main";         Description: "IR Attendance Application (required)"; Types: full compact custom; Flags: fixed
Name: "desktop";      Description: "Create Desktop Shortcut";              Types: full
Name: "startmenu";    Description: "Create Start Menu Entry";              Types: full compact

; ── What to install ──────────────────────────────────────────────────────────
[Files]
; ── Main application (entire PyInstaller dist folder) ──
Source: "{#MyAppDir}\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Components: main

; ── Microsoft Visual C++ 2015-2022 Redistributable (x64) ──
; Download vc_redist.x64.exe and place next to this .iss file before building.
; It is run silently via [Run] below so end-users never see an extra installer.
Source: "vc_redist.x64.exe"; \
    DestDir: "{tmp}"; \
    Flags: deleteafterinstall; \
    Check: VCRedistNeeded; \
    Components: main

; ── firewall helper script (allows IR Attendance through Windows Firewall) ──
Source: "allow_firewall.bat"; \
    DestDir: "{app}"; \
    Flags: ignoreversion; \
    Components: main

; ── Accept Android SDK licences helper ──
Source: "accept_licenses.bat"; \
    DestDir: "{app}"; \
    Flags: ignoreversion; \
    Components: main

; ── Shortcuts ─────────────────────────────────────────────────────────────────
[Icons]
; Desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Components: desktop

; Start Menu shortcut
Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Components: startmenu

; Start Menu - Uninstall entry
Name: "{group}\Uninstall {#MyAppName}"; \
    Filename: "{uninstallexe}"; \
    Components: startmenu

; ── Post-install actions ──────────────────────────────────────────────────────
[Run]
; 1. Install VC++ Redistributable silently (only if needed — see Check function)
Filename: "{tmp}\vc_redist.x64.exe"; \
    Parameters: "/quiet /norestart"; \
    StatusMsg: "Installing Visual C++ Runtime (required)..."; \
    Flags: waituntilterminated; \
    Check: VCRedistNeeded; \
    Components: main

; 2. Register app through Windows Firewall (so Flask server + phone mirror work)
Filename: "{app}\allow_firewall.bat"; \
    Parameters: ""; \
    StatusMsg: "Configuring firewall rules..."; \
    Flags: runhidden waituntilterminated; \
    Components: main

; 3. Accept ADB / Android SDK licences (needed for scrcpy / phone mirror)
Filename: "{app}\accept_licenses.bat"; \
    Parameters: ""; \
    StatusMsg: "Accepting Android SDK licences..."; \
    Flags: runhidden waituntilterminated; \
    Components: main

; 4. Launch app after install (optional — user can untick)
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch {#MyAppName} now"; \
    Flags: nowait postinstall skipifsilent; \
    Components: main

; ── Registry ──────────────────────────────────────────────────────────────────
[Registry]
; Tell pytesseract where tessdata lives (bundled inside app folder)
Root: HKLM; \
    Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
    ValueType: expandsz; \
    ValueName: "TESSDATA_PREFIX"; \
    ValueData: "{app}\Tesseract-OCR\tessdata"; \
    Flags: uninsdeletevalue; \
    Components: main

; Add Tesseract-OCR folder to system PATH so external tools can find it
Root: HKLM; \
    Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
    ValueType: expandsz; \
    ValueName: "Path"; \
    ValueData: "{olddata};{app}\Tesseract-OCR"; \
    Check: NeedsAddPath(ExpandConstant('{app}\Tesseract-OCR')); \
    Flags: uninsdeletevalue; \
    Components: main

; ── Cleanup on uninstall ──────────────────────────────────────────────────────
[UninstallDelete]
; Remove the entire install folder
Type: filesandordirs; Name: "{app}"

; Remove IR Attendance data directory (optional — comment out to keep user data)
; Type: filesandordirs; Name: "C:\IR Attendance"

; ── Pascal code helpers ───────────────────────────────────────────────────────
[Code]
// ── VC++ Redist check ─────────────────────────────────────
// Returns True if the VC++ 2015-2022 x64 redist is NOT already installed.
function VCRedistNeeded(): Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  // Check the VS 2022 / 2019 / 2017 / 2015 x64 redistributable registry key
  if RegQueryDWordValue(HKLM,
       'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
       'Installed', Installed) then
    Result := (Installed <> 1);
end;

// ── PATH helper ───────────────────────────────────────────
// Returns True if DirToAdd is not already in the system PATH.
function NeedsAddPath(DirToAdd: string): Boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(
      HKLM,
      'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := (Pos(';' + UpperCase(DirToAdd) + ';',
                 ';' + UpperCase(OrigPath) + ';') = 0);
end;

// ── Install complete message ───────────────────────────────
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssDone then
  begin
    // Nothing extra — launch is handled by [Run] above
  end;
end;
