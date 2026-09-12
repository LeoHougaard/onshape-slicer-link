@echo off
setlocal
cd /d "%~dp0"
if exist "%ProgramFiles%\Git\bin\bash.exe" (
  "%ProgramFiles%\Git\bin\bash.exe" scripts/setup_hosted_app.sh
) else (
  echo Git Bash is required for the one-time operator setup.
  echo See docs\deployment.md for the same steps in writing.
  pause
)
