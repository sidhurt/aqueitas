# ============================================================
# AQUEITAS BOOT SCRIPT
# Run this once from the aqueitas root folder:
#   .\start.ps1
# ============================================================

$Root = $PSScriptRoot
$BrainDir = Join-Path $Root "brain"
$Uvicorn = Join-Path $BrainDir "venv\Scripts\uvicorn.exe"

Write-Host ""
Write-Host "  ⚡ AQUEITAS BOOT SEQUENCE INITIATED" -ForegroundColor Cyan
Write-Host "  =====================================" -ForegroundColor DarkGray
Write-Host ""

# --- STEP 1: Vault (Docker) ---
Write-Host "  [1/2] Starting Sovereign Vault (Docker)..." -ForegroundColor Yellow
Set-Location $Root
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Docker failed. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}

Write-Host "  [OK] Vault is up." -ForegroundColor Green
Write-Host ""

# --- STEP 2: Brain (uvicorn) ---
Write-Host "  [2/2] Starting Intelligence Brain on http://127.0.0.1:8000 ..." -ForegroundColor Yellow

if (-Not (Test-Path $Uvicorn)) {
    Write-Host "  [ERROR] Virtual environment not found." -ForegroundColor Red
    Write-Host "          Run this first: cd brain; python -m venv venv; .\venv\Scripts\pip install -r requirements.txt" -ForegroundColor DarkYellow
    exit 1
}

# Launch uvicorn in a NEW, visible terminal window so you can see its live logs
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$BrainDir'; & '$Uvicorn' main:app --port 8000 --reload"

Write-Host "  [OK] Brain launched in a new window." -ForegroundColor Green
Write-Host ""
Write-Host "  ✅ AQUEITAS IS LIVE" -ForegroundColor Cyan
Write-Host "  =====================================" -ForegroundColor DarkGray
Write-Host "  Vault   → Docker container 'aqueitas-vault' (port 5433)" -ForegroundColor Gray
Write-Host "  Brain   → http://127.0.0.1:8000" -ForegroundColor Gray
Write-Host "  Docs    → http://127.0.0.1:8000/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "  To query: python aq.py ask `"your question here`"" -ForegroundColor Gray
Write-Host ""
