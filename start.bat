@echo off
cd /d "%~dp0"
echo ===================================================
echo  MORM - Metric Orthophoto Reference Maker
echo ===================================================
echo Starting Docker container...

docker compose up -d --build

if errorlevel 1 (
    echo [ERROR] Could not start MORM. Make sure Docker Desktop is running.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] MORM is running.
echo Web interface: http://localhost:8085
echo.
timeout /t 2 >nul
start "" "http://localhost:8085"
pause