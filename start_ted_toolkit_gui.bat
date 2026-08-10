echo "Starting Ted's Toolkit GUI"
call C:\ProgramData\Anaconda3\Scripts\activate.bat C:\Users\User\Documents\toolkit-env
cd /d "C:\Users\User\Documents\toolkit"
python -m toolkit_gui.app
echo "GUI has closed."
pause
