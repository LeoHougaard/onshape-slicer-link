; Build after scripts/build_helper.py using Inno Setup 6.
[Setup]
AppId={{C1F99D8F-4F24-4D9D-9D3B-7DCC5E37E949}
AppName=Onshape Slicer Link
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\OnshapeSlicerLink
DefaultGroupName=Onshape Slicer Link
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=OnshapeSlicerLink-Setup-x86_64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\OnshapeSlicerLink.exe

[Files]
Source: "..\dist\windows\OnshapeSlicerLink\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Onshape Slicer Link"; Filename: "{app}\OnshapeSlicerLink.exe"

[Registry]
Root: HKCU; Subkey: "Software\Classes\onshape-slicer-link"; ValueType: string; ValueName: ""; ValueData: "URL:Onshape Slicer Link"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\onshape-slicer-link"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\onshape-slicer-link\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\OnshapeSlicerLink.exe"" ""%1"""

[Run]
Filename: "{app}\OnshapeSlicerLink.exe"; Description: "Connect with Onshape"; Flags: nowait postinstall skipifsilent
