@echo off
:: MCS CVOR RMS – Windows installer
echo ============================================
echo  MCS CVOR Remote Management System
echo  Windows 11 Installer
echo ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/3] Upgrading pip...
python -m pip install --upgrade pip

echo [2/3] Installing backend dependencies...
python -m pip install flask flask-cors flask-sqlalchemy netifaces tkinterweb pillow pystray requests

echo [3/3] Optional: cefpython3 for best in-app rendering
python -m pip install cefpython3 2>nul || echo [INFO] cefpython3 not available on this platform – skipping.

echo.
echo ============================================
echo  Installation complete.
echo  Run:  python ..\MCS_desktop.py
echo ============================================
pause
