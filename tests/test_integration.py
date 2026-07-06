"""End-to-end integration test against a *running* Brain + Vault.

Skipped by default. To run:
    1. python aq.py start   (Vault + Brain up; offline providers are fine:
       EMBEDDING_PROVIDER=fake REASONING_PROVIDER=passthrough)
    2. AQUEITAS_INTEGRATION=1 pytest tests/test_integration.py

Exercises the real core loop: ingest -> dedup -> retrieve, with no psycopg2
and no direct DB access — everything goes through the API like a real client.
"""
import os
import uuid

import httpx
import pytest

BRAIN_URL = "http://127.0.0.1:8000"

pytestmark = pytest.mark.skipif(
    os.environ.get("AQUEITAS_INTEGRATION") != "1",
    reason="integration test; set AQUEITAS_INTEGRATION=1 with the Brain running",
)


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BRAIN_URL, timeout=60.0) as c:
        try:
            c.get("/docs")
        except httpx.RequestError:
            pytest.skip("Brain is not running at 127.0.0.1:8000")
        yield c


def _log_payload(commit_hash: str) -> dict:
    return {
        "project_name": "aqueitas-integration-test",
        "git_diff": (
            "diff --git a/src/checkout.py b/src/checkout.py\n"
            "--- a/src/checkout.py\n+++ b/src/checkout.py\n"
            "@@ -1,3 +1,4 @@\n def total(prices):\n"
            "-    return sum(prices)\n"
            "+    # loyalty discount\n+    return sum(prices) * 0.9\n"
        ),
        "commit_msg": "fix: apply loyalty discount in checkout totals",
        "commit_hash": commit_hash,
        "author": "Integration Test <test@aqueitas.local>",
        "committed_at": "2026-07-06T12:00:00+00:00",
    }


def test_ingest_then_dedup_then_query(client):
    commit_hash = uuid.uuid4().hex + uuid.uuid4().hex[:8]  # unique 40-char id

    # 1. First ingestion succeeds
    first = client.post("/log", json=_log_payload(commit_hash))
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "success"
    log_id = body["log_id"]

    # 2. Replaying the identical commit is a no-op, not a duplicate memory
    second = client.post("/log", json=_log_payload(commit_hash))
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["log_id"] == log_id

    # 3. The memory is retrievable with structured sources
    result = client.post("/query", json={"query": "loyalty discount checkout totals", "limit": 5})
    assert result.status_code == 200
    data = result.json()
    assert isinstance(data["sources"], list)
    assert data["answer"]


def test_malformed_payload_is_rejected_with_4xx(client):
    # Missing required fields -> validation error the replay loop can drop
    resp = client.post("/log", json={"project_name": "x"})
    assert 400 <= resp.status_code < 500
