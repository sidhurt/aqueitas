import urllib.request
import json
import os
import psycopg2
from pathlib import Path

# Load root .env (mirrors aq.py stdlib loader — no pip dependency)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# 1. Ensure a dummy project exists in the database
try:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "aqueitas_db"),
        user=os.getenv("DB_USER", "aqueitas_admin"),
        password=os.getenv("DB_PASSWORD"),
        host="127.0.0.1",
        port="5433"
    )
    cur = conn.cursor()
    cur.execute("INSERT INTO projects (name, description) VALUES ('test-project', 'Test') ON CONFLICT (name) DO UPDATE SET description='Test' RETURNING id;")
    project_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
except Exception as e:
    print(f"Failed to setup DB project: {e}")
    exit(1)

# 2. Fire the API
url = "http://127.0.0.1:8000/log"
payload = {
    "project_id": str(project_id),
    "git_diff": "diff --git a/src/utils.py b/src/utils.py\n--- a/src/utils.py\n+++ b/src/utils.py\n@@ -1,3 +1,4 @@\n def calculate_total(prices):\n-    return sum(prices)\n+    # Added discount logic to fix bug in checkout\n+    return sum(prices) * 0.9",
    "commit_msg": "Fix: Apply 10% discount to all orders in checkout logic"
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print("Status Code:", response.getcode())
        print("Response Body:", json.dumps(json.loads(response.read().decode('utf-8')), indent=2))
except urllib.error.URLError as e:
    print(f"Error calling API: {e.reason}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
