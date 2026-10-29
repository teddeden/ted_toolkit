echo "Starting python script"
rem local_env.cmd (written by setup_toolkit.bat, git-ignored) holds this machine's environment
rem activation command; without it, fall back to the original hardcoded conda paths.
if exist "%~dp0local_env.cmd" (
    call "%~dp0local_env.cmd"
) else (
    call C:\ProgramData\Anaconda3\Scripts\activate.bat C:\Users\User\Documents\toolkit-env
)
python -i "%~dp0ted_toolkit.py" %*
echo "Script has ended."
pause
