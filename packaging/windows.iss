; Build after scripts/build_helper.py using Inno Setup 6.
[Setup]
AppId={{C1F99D8F-4F24-4D9D-9D3B-7DCC5E37E949}
AppName=Onshape Slicer Link
AppVersion=0.3.1
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
Name: "{group}\Slicer Link connection setup"; Filename: "{app}\OnshapeSlicerLink.exe"; Parameters: "--setup"

[Run]
Filename: "{app}\OnshapeSlicerLink.exe"; Description: "Open local Slicer Link"; Flags: nowait postinstall skipifsilent
