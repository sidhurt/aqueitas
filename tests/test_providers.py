"""Provider-layer tests: the full offline mode (fake embeddings + passthrough
reasoning) must work with no API keys and no network."""
import asyncio
import math

from services.embedding import (
    EMBEDDING_DIMENSIONS,
    extract_context,
    fake_embedding,
    generate_embedding,
    reasoning_enabled,
)
from services.retrieval import synthesize_answer


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_offline_providers_active():
    # conftest.py pins EMBEDDING_PROVIDER=fake / REASONING_PROVIDER=passthrough
    assert not reasoning_enabled()


def test_fake_embedding_shape_and_norm():
    vec = fake_embedding("fix checkout discount logic")
    assert len(vec) == EMBEDDING_DIMENSIONS
    assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, rel_tol=1e-9)


def test_fake_embedding_is_deterministic():
    assert fake_embedding("same text") == fake_embedding("same text")


def test_fake_embedding_handles_empty_text():
    vec = fake_embedding("")
    assert len(vec) == EMBEDDING_DIMENSIONS
    assert any(x != 0.0 for x in vec)


def test_fake_embedding_similarity_tracks_token_overlap():
    query = fake_embedding("discount logic in checkout")
    related = fake_embedding("apply discount to checkout orders")
    unrelated = fake_embedding("kubernetes ingress controller tls")
    assert _dot(query, related) > _dot(query, unrelated)


def test_generate_embedding_uses_fake_provider():
    vec = asyncio.run(generate_embedding("any text at all"))
    assert vec == fake_embedding("any text at all")


def test_extract_context_passthrough_returns_commit_message():
    summary = asyncio.run(extract_context("diff --git a/x b/x\n+something", "fix: apply 10% discount"))
    assert summary == "fix: apply 10% discount"


def test_extract_context_passthrough_falls_back_to_diff():
    summary = asyncio.run(extract_context("diff --git a/x b/x\n+something", None))
    assert "diff --git" in summary


def test_synthesize_answer_empty_logs_is_honest():
    answer = asyncio.run(synthesize_answer("why did we do X?", []))
    assert answer == "The Vault contains no record of this resolution."


def test_synthesize_answer_passthrough_returns_evidence_not_prose():
    logs = [{
        "log_id": "abc-123",
        "project_name": "shop-api",
        "log_content": "COMMIT MESSAGE:\nfix: apply 10% discount\n\nDIFF:\n...",
        "created_at": "2026-07-01 10:00:00",
    }]
    answer = asyncio.run(synthesize_answer("discount logic?", logs))
    assert "shop-api" in answer
    assert "10% discount" in answer
