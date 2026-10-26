@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Open Start_BondLab.bat to launch.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.10 or later and check your internet connection.
pause
exit /b 1
