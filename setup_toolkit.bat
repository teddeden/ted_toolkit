@echo off
rem Guided first-time setup for Ted's Toolkit: creates the Python environment (conda or
rem python.org + pip) and writes local_env.cmd for the launchers. See GETTING_STARTED.md.
rem Runs setup_toolkit.ps1 with a process-only execution-policy bypass, so no system-wide
rem PowerShell policy change is needed.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_toolkit.ps1" %*
set EXITCODE=%ERRORLEVEL%
pause
exit /b %EXITCODE%
