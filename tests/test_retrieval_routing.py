"""Temporal-vs-semantic routing in the retrieval engine."""
from services.retrieval import _is_temporal_query


def test_temporal_keywords_detected():
    assert _is_temporal_query("what were my last 5 commits?")
    assert _is_temporal_query("show the most recent changes")
    assert _is_temporal_query("latest work on the API")
    assert _is_temporal_query("Recent refactors")


def test_semantic_queries_not_flagged_temporal():
    assert not _is_temporal_query("why did we switch to asyncpg?")
    assert not _is_temporal_query("how is authentication handled?")
    assert not _is_temporal_query("what does the dispatcher do?")


def test_substrings_do_not_false_positive():
    # 'blast' contains 'last' but must not trigger the temporal path
    assert not _is_temporal_query("why did the blast radius grow?")
