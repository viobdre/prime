; Inno Setup script. Built by the GitHub workflow after PyInstaller + model download.
[Setup]
AppName=PRIMETONE STEMS
AppVersion=0.3.0
AppPublisher=PRIMETONE
DefaultDirName={localappdata}\Programs\PRIMETONE STEMS
DefaultGroupName=PRIMETONE STEMS
PrivilegesRequired=lowest
OutputDir=installer_out
OutputBaseFilename=PRIMETONE_STEMS_Setup
Compression=lzma2/fast
SolidCompression=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=PRIMETONE STEMS

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"

[Files]
Source: "dist\PRIMETONE STEMS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\PRIMETONE STEMS"; Filename: "{app}\PRIMETONE STEMS.exe"
Name: "{autodesktop}\PRIMETONE STEMS"; Filename: "{app}\PRIMETONE STEMS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PRIMETONE STEMS.exe"; Description: "Launch PRIMETONE STEMS"; Flags: nowait postinstall skipifsilent
