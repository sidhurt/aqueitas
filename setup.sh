#!/usr/bin/env bash
# ============================================================
#  AQUEITAS INSTALLER — Mac / Linux
#  Run once, after you have configured your .env files.
#
#  What this does:
#    1. Verifies Python 3.10+ and Docker are installed
#    2. Verifies configuration files exist
#    3. Creates brain/venv and installs Python dependencies
#    4. Configures the global Git commit sensor
# ============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN_DIR="$ROOT/brain"
SENSOR_DIR="$ROOT/sensor"
VENV_DIR="$BRAIN_DIR/venv"
PIP_EXEC="$VENV_DIR/bin/pip"
ROOT_ENV="$ROOT/.env"
BRAIN_ENV="$BRAIN_DIR/.env"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]   ${NC} $*"; }
step() { echo -e "  ${YELLOW}[.....] ${NC}$*"; }
fail() { echo -e "\n  ${RED}[ERROR]${NC} $*\n"; exit 1; }
warn() { echo -e "  ${YELLOW}[WARN] ${NC} $*"; }

echo ""
echo -e "  ${CYAN}=============================================${NC}"
echo -e "  ${CYAN}AQUEITAS  |  Installer (Mac / Linux)${NC}"
echo -e "  ${CYAN}=============================================${NC}"
echo ""

# ── STEP 1: Check Python ──────────────────────────────────────────────────────
step "[1/4] Checking Python..."
if ! command -v python3 &>/dev/null; then
    fail "python3 is not installed.\n          Install via: https://python.org/downloads or your OS package manager."
fi

PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ) ]]; then
    fail "Python 3.10+ required. Found: $(python3 --version)\n          Download: https://python.org/downloads"
fi
ok "Python: $(python3 --version)"

# ── STEP 1b: Check Docker ─────────────────────────────────────────────────────
step "       Checking Docker..."
if ! command -v docker &>/dev/null; then
    fail "Docker is not installed.\n          Download: https://docker.com/products/docker-desktop"
fi
if ! docker info &>/dev/null; then
    fail "Docker is installed but not running. Please start Docker Desktop first."
fi
ok "Docker: $(docker --version)"

# Compose ships either as the standalone 'docker-compose' binary or the
# 'docker compose' plugin — accept both.
if command -v docker-compose &>/dev/null; then
    ok "Compose: docker-compose"
elif docker compose version &>/dev/null; then
    ok "Compose: docker compose (plugin)"
else
    fail "Docker Compose not found. Install Docker Desktop or the compose plugin."
fi

# ── STEP 2: Verify configuration was done first ───────────────────────────────
echo ""
step "[2/4] Verifying configuration files..."

if [[ ! -f "$ROOT_ENV" ]]; then
    echo -e "\n  ${RED}[ERROR]${NC} Root .env file is missing."
    echo -e "          Copy .env.example to .env and fill in your API keys:\n"
    echo -e "            cp .env.example .env"
    echo ""
    exit 1
fi
if [[ ! -f "$BRAIN_ENV" ]]; then
    echo -e "\n  ${RED}[ERROR]${NC} brain/.env file is missing."
    echo -e "          Copy brain/.env.example to brain/.env and fill in your API keys.\n"
    exit 1
fi
ok "Root .env found."
ok "brain/.env found."

# ── STEP 3: Python virtual environment + dependencies ─────────────────────────
echo ""
step "[3/4] Setting up Python environment..."

# A venv directory can exist but be unusable (e.g. a Windows venv cloned from
# another machine has Scripts/ but no bin/). Trust it only if its interpreter runs.
VENV_PY="$VENV_DIR/bin/python"
venv_healthy=false
if [[ -x "$VENV_PY" ]] && "$VENV_PY" -c "import sys" &>/dev/null; then
    venv_healthy=true
fi

if [[ "$venv_healthy" == true ]]; then
    ok "Virtual environment already exists and is healthy."
else
    if [[ -d "$VENV_DIR" ]]; then
        warn "Existing brain/venv is unusable — rebuilding it."
        rm -rf "$VENV_DIR"
    fi
    python3 -m venv "$VENV_DIR"
    ok "Virtual environment created at brain/venv"
fi

step "       Installing dependencies from brain/requirements.txt..."
"$PIP_EXEC" install -r "$BRAIN_DIR/requirements.txt" --quiet
ok "All Python dependencies installed."

# ── STEP 4: Git commit sensor ─────────────────────────────────────────────────
echo ""
step "[4/4] Configuring global Git commit sensor..."

# Ensure the post-commit hook is executable
chmod +x "$SENSOR_DIR/post-commit" 2>/dev/null || true

if git config --global core.hooksPath "$SENSOR_DIR"; then
    ok "Git sensor active. Every commit you make, anywhere, is now intercepted."
else
    warn "Could not configure Git hooks automatically."
    echo "         Run this manually:"
    echo "           git config --global core.hooksPath \"$SENSOR_DIR\""
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${CYAN}=============================================${NC}"
echo -e "  ${CYAN}AQUEITAS IS INSTALLED${NC}"
echo -e "  ${CYAN}=============================================${NC}"
echo ""
echo "  Next steps:"
echo "    1. docker-compose up -d      ← boot the Vault"
echo "    2. python3 aq.py start       ← boot the Brain"
echo "    3. python3 aq.py doctor      ← verify everything is healthy"
echo "    4. python3 aq.py ask \"...\"   ← query your technical memory"
echo ""
