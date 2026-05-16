import os
import sys
import subprocess
import argparse
import json
import time
from pathlib import Path

# ANSI Colors for a premium terminal experience
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
CYAN = "\033[96m"
RESET = "\033[0m"

ROOT_DIR = Path(__file__).parent.absolute()
BRAIN_DIR = ROOT_DIR / "brain"
VENV_DIR = BRAIN_DIR / "venv"
PYTHON_EXEC = VENV_DIR / "Scripts" / "python.exe" if os.name == "nt" else VENV_DIR / "bin" / "python"

def print_status(msg, status="info"):
    prefix = f"{BOLD}{BLUE}[AQ]{RESET}"
    if status == "success":
        prefix = f"{BOLD}{GREEN}[SUCCESS]{RESET}"
    elif status == "warning":
        prefix = f"{BOLD}{YELLOW}[WARNING]{RESET}"
    elif status == "error":
        prefix = f"{BOLD}{RED}[ERROR]{RESET}"
    elif status == "bolt":
        prefix = f"{BOLD}{CYAN}⚡{RESET}"
    
    print(f"{prefix} {msg}")

def run_cmd(cmd, cwd=ROOT_DIR, shell=True, capture=False):
    try:
        result = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=capture, text=True, check=True)
        return result.stdout.strip() if capture else True
    except subprocess.CalledProcessError as e:
        if capture:
            return e.stdout + e.stderr
        return False

def install():
    print_status("Starting Aqueitas installation...", "bolt")
    
    # 1. Create Virtual Environment
    if not VENV_DIR.exists():
        print_status("Creating virtual environment in brain/venv...")
        if not run_cmd(f"{sys.executable} -m venv venv", cwd=BRAIN_DIR):
            print_status("Failed to create virtual environment.", "error")
            return
    
    # 2. Install Dependencies
    print_status("Installing dependencies in brain/requirements.txt...")
    pip_exec = VENV_DIR / "Scripts" / "pip.exe" if os.name == "nt" else VENV_DIR / "bin" / "pip"
    if not run_cmd(f"{pip_exec} install -r requirements.txt", cwd=BRAIN_DIR):
        print_status("Failed to install dependencies.", "error")
        return
    
    # 3. Setup .env
    env_file = BRAIN_DIR / ".env"
    if not env_file.exists():
        example_env = ROOT_DIR / ".env.example"
        if example_env.exists():
            print_status("Copying .env.example to brain/.env...")
            with open(example_env, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
            print_status("Please edit brain/.env with your API keys.", "warning")
        else:
            print_status(".env.example not found. Manual .env setup required.", "warning")
            
    # 4. Setup Git Hooks
    print_status("Configuring global Git hooks...")
    if run_cmd("./setup.ps1"):
        print_status("Aqueitas is now watching your commits globally.", "success")
    else:
        print_status("Failed to run setup.ps1. Check your PowerShell execution policy.", "error")

def start():
    print_status("Launching the Sovereign Engine...", "bolt")
    
    # 1. Start Docker
    print_status("Starting Vault (Docker Compose)...")
    run_cmd("docker-compose up -d")
    
    # 2. Start Brain
    print_status("Starting Brain (FastAPI)...")
    uvicorn_cmd = f"{VENV_DIR}/Scripts/uvicorn main:app --port 8000" if os.name == "nt" else f"{VENV_DIR}/bin/uvicorn main:app --port 8000"
    
    # Run uvicorn in a new terminal window on Windows
    if os.name == "nt":
        subprocess.Popen(["start", "cmd", "/k", f"cd /d {BRAIN_DIR} && {uvicorn_cmd}"], shell=True)
    else:
        # Fallback for unix (though this script is tuned for the user's Windows setup)
        subprocess.Popen([f"{uvicorn_cmd}"], cwd=BRAIN_DIR, shell=True)
    
    print_status("Aqueitas Brain is launching in a new window.", "success")
    print_status("Run 'aq status' in a few seconds to verify connection.", "info")

def status():
    # Check Docker
    docker_check = run_cmd("docker ps --filter name=aqueitas-vault --format '{{.Status}}'", capture=True)
    vault_status = f"{GREEN}Running{RESET}" if "Up" in docker_check else f"{RED}Offline{RESET}"
    
    # Check Brain
    import urllib.request
    brain_status = f"{RED}Offline{RESET}"
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/docs", timeout=1) as r:
            if r.getcode() == 200:
                brain_status = f"{GREEN}Alive{RESET}"
    except:
        pass
        
    print(f"\n{BOLD}{CYAN}=== AQUEITAS SYSTEM STATUS ==={RESET}")
    print(f"Sovereign Vault: {vault_status}")
    print(f"Intelligence Brain: {brain_status}")
    
    # Check Git Hook
    hook_path = run_cmd("git config --global core.hooksPath", capture=True)
    sensor_status = f"{GREEN}Active{RESET}" if "sensor" in hook_path.lower() else f"{RED}Inactive{RESET}"
    print(f"Git Sensor: {sensor_status}")
    print("="*30 + "\n")

def ask(query, limit=5):
    import urllib.request
    payload = json.dumps({"query": query, "limit": limit}).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8000/query", data=payload, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.getcode() == 200:
                res_data = json.loads(response.read().decode('utf-8'))
                print(f"\n{BOLD}{CYAN}=== AQUEITAS INTELLIGENCE RETRIEVAL ==={RESET}\n")
                print(f"{BOLD}{BLUE}[ANSWER]{RESET}")
                print(f"{res_data['answer']}\n")
                print(f"{BOLD}{YELLOW}[SOURCES]{RESET}")
                if not res_data['sources']:
                    print("  No historical logs matched this query.")
                else:
                    for idx, src in enumerate(res_data['sources'], 1):
                        print(f"  {idx}. {BOLD}{src['project_name']}{RESET} (Log ID: {src['log_id']})")
                print("\n" + "="*39 + "\n")
    except Exception as e:
        print_status(f"Retreival failed: {e}", "error")

def logs(limit=10):
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8000/logs?limit={limit}", timeout=5) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                print(f"\n{BOLD}{CYAN}=== RECENT ENGINEERING LOGS ==={RESET}\n")
                for log in data:
                    print(f"{YELLOW}{log['created_at'][:19]}{RESET} | {BOLD}{log['project_name']}{RESET}")
                    # Print first line of content
                    first_line = log['log_content'].split('\n')[0]
                    print(f"  {first_line[:80]}...")
                print("\n" + "="*30 + "\n")
    except Exception as e:
        print_status(f"Failed to fetch logs: {e}", "error")

def doctor():
    print(f"\n{BOLD}{CYAN}=== AQUEITAS DIAGNOSTIC DOCTOR ==={RESET}\n")
    
    # 1. Check .env
    env_file = BRAIN_DIR / ".env"
    if not env_file.exists():
        print_status(".env file missing in brain directory.", "error")
    else:
        print_status(".env file found.", "success")
        load_dotenv(env_file)
        
        # 2. Check API Keys
        for key in ["DEEPSEEK_API_KEY", "OPENAI_API_KEY"]:
            val = os.getenv(key)
            if not val or "your_" in val:
                print_status(f"{key} is not configured properly.", "error")
            else:
                print_status(f"{key} is configured.", "success")
                
    # 3. Check Docker
    docker_check = run_cmd("docker ps --filter name=aqueitas-vault --format '{{.Status}}'", capture=True)
    if "Up" in docker_check:
        print_status("Sovereign Vault (Postgres) is online.", "success")
    else:
        print_status("Sovereign Vault is offline. Run 'aq start'.", "error")
        
    # 4. Check Python & Venv
    if PYTHON_EXEC.exists():
        print_status(f"Python virtual environment is ready.", "success")
    else:
        print_status("Virtual environment missing. Run 'aq install'.", "error")
        
    print("\n" + "="*30 + "\n")

def main():
    # Add load_dotenv import at the top level of this function or script
    from dotenv import load_dotenv
    parser = argparse.ArgumentParser(description="Aqueitas Engineering OS CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    subparsers.add_parser("install", help="Install dependencies and setup environment")
    subparsers.add_parser("start", help="Start the Vault and Brain services")
    subparsers.add_parser("status", help="Check the status of Aqueitas services")
    subparsers.add_parser("doctor", help="Run deep diagnostics")
    subparsers.add_parser("logs", help="View recent logs")
    
    ask_parser = subparsers.add_parser("ask", help="Query the technical memory")
    ask_parser.add_argument("query", help="What do you want to know?")
    ask_parser.add_argument("--limit", type=int, default=5, help="Number of sources to retrieve")
    
    args = parser.parse_args()

    if args.command == "install":
        install()
    elif args.command == "start":
        start()
    elif args.command == "status":
        status()
    elif args.command == "doctor":
        doctor()
    elif args.command == "logs":
        logs()
    elif args.command == "ask":
        ask(args.query, args.limit)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
