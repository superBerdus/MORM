Set-Location -LiteralPath $PSScriptRoot
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host " MetricScanner - Blender 1:1 Referans Tarayici" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "Docker konteyneri derlenip baslatiliyor..." -ForegroundColor Yellow
docker compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[BASARILI] MetricScanner Basariyla Baslatildi!" -ForegroundColor Green
    Write-Host "Adres: http://localhost:8085" -ForegroundColor White
    Start-Process "http://localhost:8085"
} else {
    Write-Host "`n[HATA] Docker baslatilirken sorun olustu. Docker Desktop calisiyor mu?" -ForegroundColor Red
}
