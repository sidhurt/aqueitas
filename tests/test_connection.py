import os
import psycopg2
from pathlib import Path
from psycopg2.extras import RealDictCursor

# Load root .env (mirrors aq.py stdlib loader — no pip dependency)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

def verify_vault():
    try:
        # Connect to the local sovereign vault with credentials from docker-compose.yml
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "aqueitas_db"),
            user=os.getenv("DB_USER", "aqueitas_admin"),
            password=os.getenv("DB_PASSWORD"),
            host="127.0.0.1",
            port="5433"
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify pgvector extension
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        extension = cur.fetchone()
        
        # Verify tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = [row['table_name'] for row in cur.fetchall()]
        
        print(f"--- Vault Status ---")
        print(f"pgvector Active: {bool(extension)}")
        print(f"Tables Found: {', '.join(tables)}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"CONNECTION FAILED: {e}")

if __name__ == "__main__":
    verify_vault()
