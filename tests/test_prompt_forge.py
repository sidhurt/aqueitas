"""Prompt forging for context-augmented dispatch."""
from utils.prompt_forge import forge_contextual_prompt


def test_no_context_returns_raw_prompt():
    assert forge_contextual_prompt("do the thing", []) == "do the thing"


def test_context_is_stitched_with_grounding_directive():
    logs = [{"project_name": "shop-api", "log_content": "SUMMARY:\nswitched to asyncpg"}]
    forged = forge_contextual_prompt("why asyncpg?", logs)
    assert "shop-api" in forged
    assert "switched to asyncpg" in forged
    assert "why asyncpg?" in forged
    assert "Do not hallucinate" in forged
