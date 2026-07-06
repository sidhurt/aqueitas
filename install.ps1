# ============================================================
#  AQUEITAS INSTALLER
#  Run once, after CONFIGURE_AQUEITAS.bat has been completed.
#
#  What this does:
#    1. Verifies Python 3.10+ and Docker are installed
#    2. Verifies configuration files exist (wizard ran first)
#    3. Creates brain/venv and installs Python dependencies
#    4. Configures the global Git commit sensor
# ============================================================

$Root      = $PSScriptRoot
$BrainDir  = Join-Path $Root "brain"
$SensorDir = Join-Path $Root "sensor"
$VenvDir   = Join-Path $BrainDir "venv"
$PipExec   = Join-Path $VenvDir "Scripts\pip.exe"
$RootEnv   = Join-Path $Root ".env"
$BrainEnv  = Join-Path $BrainDir ".env"

function Write-OK   { Write-Host "  [OK]    $args" -ForegroundColor Green }
function Write-Fail {
    param([string]$Msg)
    Write-Host ""
    Write-Host "  [ERROR] $Msg" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}
function Write-Step { Write-Host "  [.....] $args" -ForegroundColor Yellow }
function Write-Warn { Write-Host "  [WARN]  $args" -ForegroundColor DarkYellow }

Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host "  AQUEITAS  |  Installer" -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host ""

# ── STEP 1: Check Python ──────────────────────────────────────────────────────
Write-Step "[1/4] Checking Python..."
try {
    $pyRaw = python --version 2>&1
    if ($pyRaw -match "Python 3\.(\d+)") {
        $minor = [int]$Matches[1]
        if ($minor -lt 10) {
            Write-Fail "Python 3.10+ is required. Found: $pyRaw`n          Download: https://python.org/downloads"
        }
        Write-OK "Python: $pyRaw"
    } else {
        Write-Fail "Could not parse Python version: $pyRaw`n          Download: https://python.org/downloads"
    }
} catch {
    Write-Fail "Python is not installed or not on PATH.`n          Download: https://python.org/downloads"
}

# ── STEP 1b: Check Docker ─────────────────────────────────────────────────────
Write-Step "       Checking Docker..."
try {
    $dockerRaw = docker --version 2>&1
    Write-OK "Docker: $dockerRaw"
} catch {
    Write-Fail "Docker is not installed or not running.`n          Download: https://docker.com/products/docker-desktop"
}

# Compose ships either as the standalone 'docker-compose' binary or the
# 'docker compose' plugin — accept both.
$ComposeOK = $false
if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    $ComposeOK = $true
    Write-OK "Compose: docker-compose"
} else {
    docker compose version *> $null
    if ($LASTEXITCODE -eq 0) {
        $ComposeOK = $true
        Write-OK "Compose: docker compose (plugin)"
    }
}
if (-Not $ComposeOK) {
    Write-Fail "Docker Compose not found. Install Docker Desktop (it includes Compose)."
}

# ── STEP 2: Verify configuration was done first ───────────────────────────────
Write-Host ""
Write-Step "[2/4] Verifying configuration files..."

if (-Not (Test-Path $RootEnv)) {
    Write-Host ""
    Write-Host "  [ERROR] Root .env file is missing." -ForegroundColor Red
    Write-Host "          Please run CONFIGURE_AQUEITAS.bat first," -ForegroundColor DarkYellow
    Write-Host "          then re-run this installer." -ForegroundColor DarkYellow
    Write-Host ""
    pause
    exit 1
}
if (-Not (Test-Path $BrainEnv)) {
    Write-Host ""
    Write-Host "  [ERROR] brain/.env file is missing." -ForegroundColor Red
    Write-Host "          Please run CONFIGURE_AQUEITAS.bat first," -ForegroundColor DarkYellow
    Write-Host "          then re-run this installer." -ForegroundColor DarkYellow
    Write-Host ""
    pause
    exit 1
}
Write-OK "Root .env found."
Write-OK "brain/.env found."

# ── STEP 3: Python virtual environment + dependencies ─────────────────────────
Write-Host ""
Write-Step "[3/4] Setting up Python environment..."

# A venv directory can exist but be unusable (e.g. cloned from another
# machine, or half-created). Trust it only if its interpreter actually runs.
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvHealthy = $false
if (Test-Path $VenvPython) {
    try {
        & $VenvPython -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) { $VenvHealthy = $true }
    } catch {}
}

if ($VenvHealthy) {
    Write-OK "Virtual environment already exists and is healthy."
} else {
    if (Test-Path $VenvDir) {
        Write-Warn "Existing brain/venv is unusable — rebuilding it."
        Remove-Item -Recurse -Force $VenvDir
    }
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create virtual environment."
    }
    Write-OK "Virtual environment created at brain/venv"
}

Write-Step "       Installing dependencies from brain/requirements.txt..."
$ReqFile = Join-Path $BrainDir "requirements.txt"
& $PipExec install -r $ReqFile --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip install failed. Check brain/requirements.txt and your internet connection."
}
Write-OK "All Python dependencies installed."

# ── STEP 4: Git commit sensor ─────────────────────────────────────────────────
Write-Host ""
Write-Step "[4/4] Configuring global Git commit sensor..."

git config --global core.hooksPath $SensorDir
if ($LASTEXITCODE -eq 0) {
    Write-OK "Git sensor active. Every commit you make, anywhere, is now intercepted."
} else {
    Write-Warn "Could not configure Git hooks automatically."
    Write-Host "         Run this manually:" -ForegroundColor Gray
    Write-Host "           git config --global core.hooksPath `"$SensorDir`"" -ForegroundColor Gray
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host "  AQUEITAS IS INSTALLED" -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Double-click START_AQUEITAS.bat  ← boot the engine" -ForegroundColor Gray
Write-Host "    2. python aq.py doctor              ← verify everything is healthy" -ForegroundColor Gray
Write-Host "    3. python aq.py ask `"your question`" ← query your technical memory" -ForegroundColor Gray
Write-Host ""
pause
