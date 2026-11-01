Set-Location -LiteralPath $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host " MORM - Metric Orthophoto Reference Maker" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "Building and starting Docker container..." -ForegroundColor Yellow
docker compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] MORM is running." -ForegroundColor Green
    Write-Host "Web interface: http://localhost:8085" -ForegroundColor White
    Start-Process "http://localhost:8085"
} else {
    Write-Host "`n[ERROR] Could not start MORM. Is Docker Desktop running?" -ForegroundColor Red
}