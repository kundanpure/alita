@echo off
echo Stopping any running Alita server...
taskkill /f /im python.exe 2>nul
timeout /t 1 /nobreak >nul
echo Starting Alita...
python main.py
pause
