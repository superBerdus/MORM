@echo off
cd /d "%~dp0"
echo ===================================================
echo  MetricScanner - Blender 1:1 Referans Tarayici
echo ===================================================
echo Docker konteyneri baslatiliyor...

docker compose up -d --build

if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Docker baslatilamadi! Lutfen Docker Desktop'in acik oldugundan emin olun.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [BASARILI] MetricScanner Calisiyor!
echo Web Arayuzu: http://localhost:8085
echo.
timeout /t 2 >nul
start http://localhost:8085
pause
