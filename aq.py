import sys
import os
import subprocess
from pathlib import Path

def _env_value(content, key, default=""):
    for line in content.splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return default

def _with_database_url(content):
    if "DATABASE_URL=" in content:
        return content

    db_user = _env_value(content, "DB_USER", "aqueitas_admin")
    db_password = _env_value(content, "DB_PASSWORD", "sovereign_password_123")
    db_name = _env_value(content, "DB_NAME", "aqueitas_db")
    db_host = _env_value(content, "DB_HOST", "127.0.0.1")
    db_port = _env_value(content, "DB_PORT", "5433")
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return content.rstrip() + f"\nDATABASE_URL={database_url}\n"

def get_venv_python():
    base = Path(__file__).parent.absolute()
    if os.name == "nt":
        return base / "brain" / "venv" / "Scripts" / "python.exe"
    return base / "brain" / "venv" / "bin" / "python"

def run_configure():
    print("=== AQUEITAS SETUP WIZARD ===")
    root_dir = Path(__file__).parent.absolute()
    env_example = root_dir / ".env.example"
    env_file = root_dir / ".env"
    brain_env_file = root_dir / "brain" / ".env"
    
    if env_file.exists():
        print(".env already exists. Skipping root configuration.")
    else:
        openai_key = input("Enter your OpenAI API Key (or press Enter to skip): ").strip()
        deepseek_key = input("Enter your DeepSeek API Key (or press Enter to skip): ").strip()
        
        content = env_example.read_text(encoding="utf-8") if env_example.exists() else ""
        content = content.replace("your_openai_api_key_here", openai_key or "your_openai_api_key_here")
        content = content.replace("your_deepseek_api_key_here", deepseek_key or "your_deepseek_api_key_here")
        content = _with_database_url(content)
        
        env_file.write_text(content, encoding="utf-8")
        print(f"Created {env_file}")
        
    if brain_env_file.exists():
        print("brain/.env already exists. Skipping.")
    else:
        brain_env_file.parent.mkdir(parents=True, exist_ok=True)
        content = _with_database_url(env_file.read_text(encoding="utf-8"))
        brain_env_file.write_text(content, encoding="utf-8")
        print(f"Created {brain_env_file}")
    
    print("Configuration complete!")

def run_install():
    root_dir = Path(__file__).parent.absolute()
    if os.name == "nt":
        script = root_dir / "install.ps1"
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=False)
    else:
        script = root_dir / "setup.sh"
        subprocess.run(["bash", str(script)], check=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "configure":
            run_configure()
            sys.exit(0)
        elif sys.argv[1] == "install":
            run_install()
            sys.exit(0)

    venv_python = get_venv_python()
    if venv_python.exists() and str(venv_python) != sys.executable:
        # Re-execute using the venv python
        sys.exit(subprocess.call([str(venv_python)] + sys.argv))
    
    try:
        from cli.main import app
    except ImportError:
        print("Error: CLI dependencies not found. Please run INSTALL_AQUEITAS.bat (or python aq.py install) first.")
        sys.exit(1)
        
    app()
