@echo off
echo Running Ted's Toolkit regression suite...
rem See start_ted_toolkit.bat: local_env.cmd (from setup_toolkit.bat) overrides the default env.
if exist "%~dp0local_env.cmd" (
    call "%~dp0local_env.cmd"
) else (
    call C:\ProgramData\Anaconda3\Scripts\activate.bat C:\Users\User\Documents\toolkit-env
)
python "%~dp0run_regression_tests.py"
set EXITCODE=%ERRORLEVEL%
echo.
echo Regression run finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
