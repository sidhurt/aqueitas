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

# Diffs above this size are truncated before leaving the machine: they blow past
# LLM context limits and become poison entries that can never be ingested.
MAX_DIFF_CHARS = 50_000


def run_cmd(args):
    try:
        result = subprocess.run(
            args, capture_output=True,
            text=True, check=True, encoding="utf-8", errors="replace"
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def cap_diff(git_diff: str, diff_stat: str, max_chars: int = MAX_DIFF_CHARS) -> str:
    """Cap oversized diffs, preserving the per-file stat summary and the head of
    the diff so intent extraction still has the most useful signal."""
    if len(git_diff) <= max_chars:
        return git_diff
    original_size = len(git_diff)
    return (
        f"{diff_stat}\n\n"
        f"{git_diff[:max_chars]}\n\n"
        f"[Aqueitas sensor: diff truncated from {original_size} to {max_chars} characters]"
    )


def build_payload(project_name, commit_hash, commit_msg, author, committed_at, git_diff, diff_stat):
    return {
        "project_name": project_name,
        "git_diff":     cap_diff(git_diff, diff_stat),
        "commit_msg":   commit_msg,
        "commit_hash":  commit_hash or None,
        "author":       author or None,
        "committed_at": committed_at or None,
    }


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
    # 1. Project identity: repository root folder name (hooks run at the top of
    #    the working tree, but rev-parse is robust if that ever changes)
    toplevel = run_cmd(["git", "rev-parse", "--show-toplevel"])
    project_name = os.path.basename(toplevel) if toplevel else os.path.basename(os.getcwd())

    # 2. Structured commit metadata — the hash is the decision's stable identity
    commit_hash  = run_cmd(["git", "rev-parse", "HEAD"])
    commit_msg   = run_cmd(["git", "log", "-1", "--pretty=%B"])
    author       = run_cmd(["git", "log", "-1", "--pretty=%an <%ae>"])
    committed_at = run_cmd(["git", "log", "-1", "--pretty=%cI"])

    # 3. The latest commit diff (HEAD~1 to HEAD); fall back for the initial commit
    git_diff  = run_cmd(["git", "diff", "HEAD~1", "HEAD"])
    diff_stat = run_cmd(["git", "diff", "--stat", "HEAD~1", "HEAD"])
    if not git_diff:
        git_diff  = run_cmd(["git", "show", "HEAD"])
        diff_stat = run_cmd(["git", "show", "--stat", "HEAD"])

    payload = build_payload(project_name, commit_hash, commit_msg, author, committed_at, git_diff, diff_stat)

    url  = "http://127.0.0.1:8000/log"
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    # 4. Fire request synchronously to maintain tactical feedback loop
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
