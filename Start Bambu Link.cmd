@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_link.ps1" -Slicer bambu
if errorlevel 1 pause
