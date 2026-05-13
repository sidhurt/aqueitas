#!/usr/bin/env python3
import urllib.request
import json
import os
import subprocess
import sys

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def main():
    # 1. Get project name from current directory
    cwd = os.getcwd()
    project_name = os.path.basename(cwd)

    # 2. Get the latest commit diff (HEAD~1 to HEAD)
    git_diff = run_cmd("git diff HEAD~1 HEAD")
    if not git_diff:
        # Initial commit or no diff
        git_diff = run_cmd("git show HEAD")
    
    # 3. Get the commit message
    commit_msg = run_cmd("git log -1 --pretty=%B")

    # 4. Prepare payload
    payload = {
        "project_name": project_name,
        "git_diff": git_diff,
        "commit_msg": commit_msg
    }

    url = "http://127.0.0.1:8000/log"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

    # 5. Fire request synchronously to maintain tactical feedback loop
    print(f"[Aqueitas] Sensor triggered. Synchronizing '{project_name}' log to Sovereign Vault...")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.getcode() == 200:
                print(f"[Aqueitas] Sync Complete. The Intelligence Engine has saved the embedding.")
            else:
                print(f"[Aqueitas] Warning: Received status {response.getcode()} from Brain.")
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError) or "Connection refused" in str(e.reason) or "No connection" in str(e.reason):
            print("[Aqueitas] Brain is offline. Commit saved, but log was NOT synced.")
        else:
            print(f"[Aqueitas] Error: {e.reason}")
    except Exception as e:
        print(f"[Aqueitas] Unexpected error: {e}")

if __name__ == "__main__":
    main()
