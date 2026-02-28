@echo off
cd /d "%~dp0"
echo =========================================
echo  TruthSeeker Plus Web App
echo =========================================
echo.
echo Installing / updating dependencies...
python -m pip install flask playwright requests fpdf2 --quiet
if errorlevel 1 (echo ERROR: pip install failed & pause & exit /b 1)

echo Installing Playwright browser (first run only)...
python -m playwright install chromium
if errorlevel 1 (echo WARNING: Playwright browser install failed. Age gate auto-handling disabled.)

echo.
echo Starting TruthSeeker Plus server...
echo Your browser will open automatically at http://localhost:5173
echo Close this window to stop the server.
echo.
python server.py
pause
