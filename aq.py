import os
import sys
import subprocess
import argparse
import json
import re
import secrets
import string
import time
from pathlib import Path

# ── Force UTF-8 output on Windows (prevents cp1252 UnicodeEncodeError) ───────
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Stdlib .env loader (no pip dependency — works before venv exists) ─────────
def load_dotenv(path):
    """Parse a .env file and inject values into os.environ. Zero dependencies."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, val)
    except (OSError, IOError):
        pass  # file doesn't exist yet — safe to ignore

# ── ANSI colors ───────────────────────────────────────────────────────────────
BLUE  = "\033[94m"
GREEN = "\033[92m"
YELLOW= "\033[93m"
RED   = "\033[91m"
BOLD  = "\033[1m"
CYAN  = "\033[96m"
GRAY  = "\033[90m"
RESET = "\033[0m"

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).parent.absolute()
BRAIN_DIR  = ROOT_DIR / "brain"
SENSOR_DIR = ROOT_DIR / "sensor"
VENV_DIR   = BRAIN_DIR / "venv"
PYTHON_EXEC = VENV_DIR / "Scripts" / "python.exe" if os.name == "nt" else VENV_DIR / "bin" / "python"
PIP_EXEC    = VENV_DIR / "Scripts" / "pip.exe"    if os.name == "nt" else VENV_DIR / "bin" / "pip"


# ── Utilities ─────────────────────────────────────────────────────────────────
def print_status(msg, status="info"):
    icons = {
        "info":    f"{BOLD}{BLUE}[AQ]{RESET}",
        "success": f"{BOLD}{GREEN}[OK]{RESET}",
        "warning": f"{BOLD}{YELLOW}[WARN]{RESET}",
        "error":   f"{BOLD}{RED}[ERROR]{RESET}",
        "bolt":    f"{BOLD}{CYAN}**{RESET}",
        "step":    f"{BOLD}{CYAN}>>{RESET}",
    }
    print(f"  {icons.get(status, icons['info'])} {msg}")

def run_cmd(cmd, cwd=ROOT_DIR, shell=True, capture=False):
    try:
        result = subprocess.run(
            cmd, cwd=cwd, shell=shell,
            capture_output=capture, text=True, check=True
        )
        return result.stdout.strip() if capture else True
    except subprocess.CalledProcessError as e:
        if capture:
            return (e.stdout or "") + (e.stderr or "")
        return False

def divider(char="─", width=45):
    print(f"  {GRAY}{char * width}{RESET}")


# ── configure ─────────────────────────────────────────────────────────────────
def configure():
    """
    Interactive wizard. Writes two files:
      • root .env        → consumed by docker-compose.yml  (DB_USER / DB_PASSWORD / DB_NAME)
      • brain/.env       → consumed by FastAPI              (DATABASE_URL / API keys)
    Uses stdlib only — safe to run before the venv exists.
    """
    print()
    print(f"  {BOLD}{CYAN}⚡  AQUEITAS SETUP WIZARD{RESET}")
    divider("═")
    print()
    print(f"  {GRAY}This wizard writes your .env files so you never edit them manually.{RESET}")
    print(f"  {GRAY}Get your keys from:{RESET}")
    print(f"  {GRAY}  OpenAI   → https://platform.openai.com/api-keys{RESET}")
    print(f"  {GRAY}  DeepSeek → https://platform.deepseek.com/api_keys{RESET}")
    print()

    brain_env = BRAIN_DIR / ".env"
    root_env  = ROOT_DIR  / ".env"

    # ── Reconfigure guard ──────────────────────────────────────────────────────
    if brain_env.exists():
        content = brain_env.read_text()
        if "sk-" in content and "your_" not in content and "your-" not in content:
            print_status("brain/.env already has real keys configured.", "warning")
            resp = input("  Reconfigure from scratch? (y/N): ").strip().lower()
            if resp != "y":
                print_status("Configuration unchanged. Run 'python aq.py install' to continue.", "info")
                print()
                return

    # ── Step 1: OpenAI key ────────────────────────────────────────────────────
    print(f"  {BOLD}Step 1 of 3  —  OpenAI API Key{RESET}")
    print(f"  {GRAY}Used for text-embedding-3-small (embedding commits into the Vault){RESET}")
    while True:
        openai_key = input("  Enter key: ").strip()
        if openai_key.startswith("sk-"):
            print_status("Key format valid.", "success")
            break
        print_status("OpenAI keys begin with 'sk-'. Please try again.", "warning")
    print()

    # ── Step 2: DeepSeek key ──────────────────────────────────────────────────
    print(f"  {BOLD}Step 2 of 3  —  DeepSeek API Key{RESET}")
    print(f"  {GRAY}Used for deepseek-chat (reasoning about what a commit means){RESET}")
    while True:
        deepseek_key = input("  Enter key: ").strip()
        if deepseek_key.startswith("sk-"):
            print_status("Key format valid.", "success")
            break
        print_status("DeepSeek keys begin with 'sk-'. Please try again.", "warning")
    print()

    # ── Step 3: DB password ───────────────────────────────────────────────────
    print(f"  {BOLD}Step 3 of 3  —  Database Password{RESET}")
    print(f"  {GRAY}Secures your local PostgreSQL Sovereign Vault.{RESET}")
    print(f"  {GRAY}Press Enter to auto-generate a strong password.{RESET}")
    db_pass_input = input("  Password (or Enter to generate): ").strip()
    if not db_pass_input:
        alphabet    = string.ascii_letters + string.digits + "!#$%^&*"
        db_password = "".join(secrets.choice(alphabet) for _ in range(22))
        print_status(f"Generated: {BOLD}{db_password}{RESET}", "success")
    else:
        db_password = db_pass_input
        print_status("Password accepted.", "success")
    print()

    # ── Constants ──────────────────────────────────────────────────────────────
    db_user = "aqueitas_admin"
    db_name = "aqueitas_db"
    db_host = "127.0.0.1"
    db_port = "5433"

    # ── Write root/.env (Docker) ───────────────────────────────────────────────
    root_env_content = (
        "# ============================================================\n"
        "# AQUEITAS — DOCKER COMPOSE ENVIRONMENT\n"
        "# Auto-generated by: python aq.py configure\n"
        "# DO NOT commit this file — it is in .gitignore\n"
        "# ============================================================\n"
        "\n"
        f"DB_USER={db_user}\n"
        f"DB_PASSWORD={db_password}\n"
        f"DB_NAME={db_name}\n"
    )

    # ── Write brain/.env (FastAPI) ─────────────────────────────────────────────
    brain_env_content = (
        "# ============================================================\n"
        "# AQUEITAS — BRAIN ENVIRONMENT\n"
        "# Auto-generated by: python aq.py configure\n"
        "# DO NOT commit this file — it is in .gitignore\n"
        "# ============================================================\n"
        "\n"
        "# --- Database (mirrors root .env for Docker) ---\n"
        f"DB_USER={db_user}\n"
        f"DB_PASSWORD={db_password}\n"
        f"DB_NAME={db_name}\n"
        f"DATABASE_URL=postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}\n"
        "\n"
        "# --- OpenAI (Embeddings: text-embedding-3-small) ---\n"
        f"OPENAI_API_KEY={openai_key}\n"
        "\n"
        "# --- DeepSeek (Reasoning: deepseek-chat) ---\n"
        f"DEEPSEEK_API_KEY={deepseek_key}\n"
    )

    divider()
    print(f"  Writing .env (Docker)  ...", end="  ", flush=True)
    root_env.write_text(root_env_content, encoding="utf-8")
    print(f"{GREEN}done{RESET}")

    print(f"  Writing brain/.env     ...", end="  ", flush=True)
    brain_env.write_text(brain_env_content, encoding="utf-8")
    print(f"{GREEN}done{RESET}")

    print()
    divider("═")
    print(f"  {BOLD}{GREEN}✅  Configuration complete!{RESET}")
    divider("─")
    print(f"  {GRAY}Next step — run the installer:{RESET}")
    if os.name == "nt":
        print(f"  {BOLD}  Double-click: INSTALL_AQUEITAS.bat{RESET}")
        print(f"  {GRAY}  Or terminal:  python aq.py install{RESET}")
    else:
        print(f"  {BOLD}  python3 aq.py install{RESET}")
    print()


# ── install ───────────────────────────────────────────────────────────────────
def install():
    """
    Bootstrap the Python environment and Git sensor.
    Requires configure() to have been run first.
    """
    print()
    print_status("Starting Aqueitas installation...", "bolt")
    print()

    # ── Gate: must configure first ────────────────────────────────────────────
    brain_env = BRAIN_DIR / ".env"
    root_env  = ROOT_DIR  / ".env"
    if not brain_env.exists() or not root_env.exists():
        print_status("Configuration files not found.", "error")
        print_status("Run 'python aq.py configure' first, then re-run install.", "warning")
        return

    # ── 1. Create venv ────────────────────────────────────────────────────────
    print_status("Creating virtual environment in brain/venv...", "step")
    if not VENV_DIR.exists():
        if not run_cmd(f"{sys.executable} -m venv venv", cwd=BRAIN_DIR):
            print_status("Failed to create virtual environment.", "error")
            return
        print_status("Virtual environment created.", "success")
    else:
        print_status("Virtual environment already exists — skipping.", "info")

    # ── 2. Install dependencies ───────────────────────────────────────────────
    print_status("Installing dependencies from brain/requirements.txt...", "step")
    if not run_cmd(f"{PIP_EXEC} install -r requirements.txt --quiet", cwd=BRAIN_DIR):
        print_status("pip install failed. Check brain/requirements.txt.", "error")
        return
    print_status("All dependencies installed.", "success")

    # ── 3. Configure Git sensor ───────────────────────────────────────────────
    print_status("Configuring global Git sensor...", "step")
    sensor_path = str(SENSOR_DIR).replace("\\", "/")
    if run_cmd(f'git config --global core.hooksPath "{sensor_path}"'):
        print_status("Git sensor is active — all commits will be intercepted.", "success")
    else:
        print_status(
            f"Could not set Git hooks automatically. Run manually:\n"
            f"    git config --global core.hooksPath \"{sensor_path}\"",
            "warning"
        )

    print()
    divider("═")
    print(f"  {BOLD}{GREEN}✅  Aqueitas installed!{RESET}")
    divider("─")
    print(f"  {GRAY}Start the engine:{RESET}")
    if os.name == "nt":
        print(f"  {BOLD}  Double-click: START_AQUEITAS.bat{RESET}")
        print(f"  {GRAY}  Or terminal:  python aq.py start{RESET}")
    else:
        print(f"  {BOLD}  python3 aq.py start{RESET}")
    print(f"  {GRAY}  Verify:       python{'3' if os.name != 'nt' else ''} aq.py doctor{RESET}")
    print()


# ── start ─────────────────────────────────────────────────────────────────────
def start():
    print_status("Launching the Sovereign Engine...", "bolt")

    print_status("Starting Vault (Docker Compose)...", "step")
    if not run_cmd("docker-compose up -d"):
        print_status("Docker failed. Is Docker Desktop running?", "error")
        return
    print_status("Vault is up.", "success")

    print_status("Launching Brain (FastAPI) in a new window...", "step")
    uvicorn_exec = VENV_DIR / "Scripts" / "uvicorn.exe" if os.name == "nt" else VENV_DIR / "bin" / "uvicorn"
    if not uvicorn_exec.exists():
        print_status(
            "Virtual environment not found. Run 'python aq.py install' first.", "error"
        )
        return

    if os.name == "nt":
        cmd = (
            f"Start-Process powershell -ArgumentList '-NoExit','-Command',"
            f"\"Set-Location '{BRAIN_DIR}'; & '{uvicorn_exec}' main:app --host 0.0.0.0 --port 8000 --reload\""
        )
        subprocess.Popen(["powershell", "-Command", cmd], shell=False)
    else:
        subprocess.Popen(
            [str(uvicorn_exec), "main:app", "--port", "8000", "--reload"],
            cwd=BRAIN_DIR
        )

    print_status("Brain is launching. Give it 3 seconds, then run: python aq.py status", "success")

    # ── Offline-queue reminder ─────────────────────────────────────────────────
    queue_file = SENSOR_DIR / "queue.jsonl"
    if queue_file.exists():
        try:
            pending = sum(1 for line in queue_file.read_text(encoding="utf-8").splitlines() if line.strip())
            if pending:
                print()
                print_status(
                    f"{BOLD}{YELLOW}{pending} commit(s){RESET} are queued from when the Brain was offline.",
                    "warning"
                )
                print_status("Once the Brain is live, run: python aq.py replay", "info")
        except Exception:
            pass


# ── status ────────────────────────────────────────────────────────────────────
def status():
    import urllib.request

    # Docker / Vault
    docker_out  = run_cmd("docker ps --filter name=aqueitas-vault --format {{.Status}}", capture=True)
    vault_ok    = isinstance(docker_out, str) and "Up" in docker_out
    vault_label = f"{GREEN}Running{RESET}" if vault_ok else f"{RED}Offline{RESET}"

    # Brain (FastAPI)
    brain_label = f"{RED}Offline{RESET}"
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/docs", timeout=2) as r:
            if r.getcode() == 200:
                brain_label = f"{GREEN}Alive{RESET}"
    except Exception:
        pass

    # Git sensor
    hook_path   = run_cmd("git config --global core.hooksPath", capture=True) or ""
    sensor_ok   = "sensor" in hook_path.lower()
    sensor_label= f"{GREEN}Active{RESET}" if sensor_ok else f"{YELLOW}Inactive{RESET}"

    print()
    print(f"  {BOLD}{CYAN}=== AQUEITAS SYSTEM STATUS ==={RESET}")
    divider()
    print(f"  Sovereign Vault    {vault_label}")
    print(f"  Intelligence Brain {brain_label}")
    print(f"  Git Sensor         {sensor_label}")
    divider()
    print()


# ── doctor ────────────────────────────────────────────────────────────────────
def doctor():
    print()
    print(f"  {BOLD}{CYAN}=== AQUEITAS DIAGNOSTIC DOCTOR ==={RESET}")
    divider()

    # .env files
    brain_env = BRAIN_DIR / ".env"
    root_env  = ROOT_DIR  / ".env"

    if not root_env.exists():
        print_status("Root .env (Docker) is missing. Run 'python aq.py configure'.", "error")
    else:
        print_status("Root .env (Docker) found.", "success")

    if not brain_env.exists():
        print_status("brain/.env (FastAPI) is missing. Run 'python aq.py configure'.", "error")
    else:
        print_status("brain/.env (FastAPI) found.", "success")
        load_dotenv(brain_env)

        for key in ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "DATABASE_URL"]:
            val = os.getenv(key, "")
            if not val or "your_" in val or "your-" in val:
                print_status(f"{key} is not configured properly.", "error")
            else:
                masked = val[:8] + "..." if len(val) > 8 else val
                print_status(f"{key} is set ({masked}).", "success")

    # Docker / Vault
    docker_out = run_cmd("docker ps --filter name=aqueitas-vault --format {{.Status}}", capture=True)
    if isinstance(docker_out, str) and "Up" in docker_out:
        print_status("Sovereign Vault (Postgres) is online.", "success")
    else:
        print_status("Sovereign Vault is offline. Run 'python aq.py start'.", "error")

    # Python venv
    if PYTHON_EXEC.exists():
        print_status("Python virtual environment is ready.", "success")
    else:
        print_status("Virtual environment missing. Run 'python aq.py install'.", "error")

    # Git sensor
    hook_path = run_cmd("git config --global core.hooksPath", capture=True) or ""
    if "sensor" in hook_path.lower():
        print_status("Git sensor hook is configured.", "success")
    else:
        print_status("Git sensor hook is NOT set. Run 'python aq.py install'.", "error")

    divider()
    print()


# ── ask ───────────────────────────────────────────────────────────────────────
def ask(query, limit=5):
    import urllib.request
    payload = json.dumps({"query": query, "limit": limit}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/query",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            print(f"\n{BOLD}{CYAN}=== AQUEITAS INTELLIGENCE RETRIEVAL ==={RESET}\n")
            print(f"{BOLD}{BLUE}[ANSWER]{RESET}")
            print(f"{res_data['answer']}\n")
            print(f"{BOLD}{YELLOW}[SOURCES]{RESET}")
            if not res_data.get("sources"):
                print("  No historical logs matched this query.")
            else:
                for idx, src in enumerate(res_data["sources"], 1):
                    print(f"  {idx}. {BOLD}{src['project_name']}{RESET} (Log ID: {src['log_id']})")
            print("\n" + "=" * 39 + "\n")
    except Exception as e:
        print_status(f"Retrieval failed: {e}", "error")


# ── logs ──────────────────────────────────────────────────────────────────────
def logs(limit=10):
    import urllib.request
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:8000/logs?limit={limit}", timeout=5
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
            print(f"\n{BOLD}{CYAN}=== RECENT ENGINEERING LOGS ==={RESET}\n")
            for log in data:
                print(f"  {YELLOW}{log['created_at'][:19]}{RESET}  {BOLD}{log['project_name']}{RESET}")
                first_line = log["log_content"].split("\n")[0]
                print(f"  {GRAY}{first_line[:80]}...{RESET}")
            print("\n" + "=" * 30 + "\n")
    except Exception as e:
        print_status(f"Failed to fetch logs: {e}", "error")


# ── replay ────────────────────────────────────────────────────────────────────
def replay():
    """
    Re-ingests commits that were queued while the Brain was offline.
    Reads sensor/queue.jsonl, POSTs each entry to the live Brain,
    and removes successfully replayed entries from the queue.
    """
    import urllib.request
    import urllib.error

    queue_file = SENSOR_DIR / "queue.jsonl"

    print()
    print(f"  {BOLD}{CYAN}⚡  AQUEITAS OFFLINE QUEUE REPLAY{RESET}")
    divider("═")

    if not queue_file.exists():
        print_status("Queue is empty — nothing to replay.", "success")
        print()
        return

    raw_lines = [line.strip() for line in queue_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not raw_lines:
        print_status("Queue is empty — nothing to replay.", "success")
        print()
        return

    print_status(f"Found {BOLD}{len(raw_lines)}{RESET} queued commit(s). Replaying...", "info")
    divider()

    failed_lines = []
    replayed = 0

    for idx, line in enumerate(raw_lines, 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            print_status(f"[{idx}] Skipping malformed queue entry.", "warning")
            continue

        # Strip queue metadata — Brain only needs these three fields
        payload = {
            "project_name": entry.get("project_name", "unknown"),
            "git_diff":     entry.get("git_diff", ""),
            "commit_msg":   entry.get("commit_msg", ""),
        }
        queued_at = entry.get("queued_at", "unknown time")
        label = f"{BOLD}{payload['project_name']}{RESET} (queued {queued_at[:19]})"

        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            "http://127.0.0.1:8000/log",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.getcode() == 200:
                    print_status(f"[{idx}/{len(raw_lines)}] Replayed → {label}", "success")
                    replayed += 1
                else:
                    print_status(f"[{idx}/{len(raw_lines)}] Brain returned {response.getcode()} — keeping in queue.", "warning")
                    failed_lines.append(line)
        except urllib.error.URLError as e:
            reason = str(e.reason)
            if "Connection refused" in reason or "No connection" in reason:
                print_status(f"[{idx}/{len(raw_lines)}] Brain is offline — stopping replay.", "error")
                # Keep this and all remaining entries
                failed_lines.extend(raw_lines[idx - 1:])
                break
            else:
                print_status(f"[{idx}/{len(raw_lines)}] Network error ({reason}) — keeping in queue.", "warning")
                failed_lines.append(line)
        except Exception as e:
            print_status(f"[{idx}/{len(raw_lines)}] Unexpected error ({e}) — keeping in queue.", "warning")
            failed_lines.append(line)

    # ── Rewrite queue with only the entries that failed ───────────────────────
    if failed_lines:
        queue_file.write_text("\n".join(failed_lines) + "\n", encoding="utf-8")
    else:
        queue_file.unlink(missing_ok=True)

    divider("═")
    print_status(f"{replayed}/{len(raw_lines)} commit(s) successfully replayed.",
                 "success" if replayed == len(raw_lines) else "warning")
    if failed_lines:
        print_status(f"{len(failed_lines)} commit(s) remain in queue for next replay.", "info")
    print()


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="aq",
        description="Aqueitas Engineering OS — CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Typical first-time setup:\n"
            "  1. python aq.py configure   << interactive wizard (run once)\n"
            "  2. python aq.py install     << bootstrap venv + git hooks\n"
            "  3. python aq.py start       << boot vault + brain\n"
            "  4. python aq.py status      << verify everything is live\n"
            "\n"
            "On Mac / Linux, use python3 instead of python:\n"
            "  python3 aq.py configure\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    sub.add_parser("configure", help="Interactive wizard — write .env files from API keys")
    sub.add_parser("install",   help="Create venv, install deps, configure Git sensor")
    sub.add_parser("start",     help="Start Vault (Docker) and Brain (FastAPI)")
    sub.add_parser("status",    help="Quick health-check of all three services")
    sub.add_parser("doctor",    help="Deep diagnostics — keys, files, hooks, connectivity")
    sub.add_parser("logs",      help="View the 10 most recent ingested commit logs")
    sub.add_parser("replay",    help="Re-ingest commits queued while the Brain was offline")

    ask_p = sub.add_parser("ask", help="Query your technical memory")
    ask_p.add_argument("query",   help="Natural-language question")
    ask_p.add_argument("--limit", type=int, default=5, help="Max sources to return (default 5)")

    args = parser.parse_args()

    dispatch = {
        "configure": configure,
        "install":   install,
        "start":     start,
        "status":    status,
        "doctor":    doctor,
        "logs":      logs,
        "replay":    replay,
    }

    if args.command in dispatch:
        dispatch[args.command]()
    elif args.command == "ask":
        ask(args.query, args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
