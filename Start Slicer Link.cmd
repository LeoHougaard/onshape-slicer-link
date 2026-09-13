@echo off
setlocal
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\OnshapeSlicerLink\OnshapeSlicerLink.exe" (
  start "" "%LOCALAPPDATA%\Programs\OnshapeSlicerLink\OnshapeSlicerLink.exe"
) else (
  start "" ".venv\Scripts\pythonw.exe" -m slicer_link.local
)
