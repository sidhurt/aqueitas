#!/usr/bin/env python3
import urllib.request
import urllib.error
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

# ── Queue file lives next to this script so it is always findable ─────────────
SCRIPT_DIR = Path(__file__).parent.absolute()
QUEUE_FILE  = SCRIPT_DIR / "queue.jsonl"


def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, check=True, encoding="utf-8", errors="replace"
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def write_to_queue(payload: dict) -> None:
    """Append a commit payload to the local offline queue."""
    entry = {**payload, "queued_at": datetime.now(timezone.utc).isoformat()}
    try:
        with open(QUEUE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[Aqueitas] Commit queued locally. Run 'python aq.py replay' when Brain is running.")
    except Exception as write_err:
        print(f"[Aqueitas] WARNING: Could not write to queue ({write_err}). This commit will not be ingested.")


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
        "git_diff":     git_diff,
        "commit_msg":   commit_msg,
    }

    url  = "http://127.0.0.1:8000/log"
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    # 5. Fire request synchronously to maintain tactical feedback loop
    print(f"[Aqueitas] Sensor triggered. Synchronizing '{project_name}' log to Sovereign Vault...")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.getcode() == 200:
                print("[Aqueitas] Sync Complete. The Intelligence Engine has saved the embedding.")
            else:
                print(f"[Aqueitas] Warning: Received status {response.getcode()} from Brain.")
                write_to_queue(payload)

    except urllib.error.URLError as e:
        reason = str(e.reason)
        if isinstance(e.reason, TimeoutError) or "Connection refused" in reason or "No connection" in reason:
            print("[Aqueitas] Brain is offline.")
            write_to_queue(payload)
        else:
            print(f"[Aqueitas] Network error: {reason}")
            write_to_queue(payload)

    except Exception as e:
        print(f"[Aqueitas] Unexpected error: {e}")
        write_to_queue(payload)


if __name__ == "__main__":
    main()
