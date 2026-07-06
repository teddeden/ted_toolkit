@echo off
echo Running Ted's Toolkit regression suite...
call C:\ProgramData\Anaconda3\Scripts\activate.bat C:\Users\User\Documents\toolkit-env
python "%~dp0run_regression_tests.py"
set EXITCODE=%ERRORLEVEL%
echo.
echo Regression run finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
