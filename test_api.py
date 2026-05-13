import urllib.request
import json
import psycopg2

# 1. Ensure a dummy project exists in the database
try:
    conn = psycopg2.connect(
        dbname="aqueitas_db",
        user="aqueitas_admin",
        password="sovereign_password_123",
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
