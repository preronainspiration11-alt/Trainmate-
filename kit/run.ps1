# One-click launcher for TrainMate. Run with:
#   powershell -ExecutionPolicy Bypass -File .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
if (-not $env:ANTHROPIC_API_KEY) {
  $env:ANTHROPIC_API_KEY = Read-Host "Paste your Anthropic API key (sk-ant-...)"
}
if (-not $env:MODEL) { $env:MODEL = "claude-sonnet-5" }   # change if your Console shows a different id
if (-not (Test-Path ".deps_ok")) {
  Write-Host "Installing dependencies (first run only)..." -ForegroundColor Cyan
  python -m pip install -r requirements.txt
  if ($LASTEXITCODE -eq 0) { New-Item -ItemType File -Name ".deps_ok" | Out-Null }
}
Write-Host ""
Write-Host "Starting TrainMate on http://localhost:8000" -ForegroundColor Green
Write-Host "KEEP THIS WINDOW OPEN, then open client.html in your browser." -ForegroundColor Yellow
Write-Host ""
python -m uvicorn server:app --port 8000
