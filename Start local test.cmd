@echo off
setlocal
cd /d "%~dp0"
title Onshape Slicer Link - local test
".venv\Scripts\python.exe" -m scripts.local_test
if errorlevel 1 pause
