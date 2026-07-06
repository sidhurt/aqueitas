"""Sensor payload construction and diff capping (pure logic, no git needed)."""
import importlib.util
from pathlib import Path

_SENSOR_PATH = Path(__file__).parent.parent / "sensor" / "post-commit.py"
_spec = importlib.util.spec_from_file_location("aqueitas_sensor", _SENSOR_PATH)
sensor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sensor)


def test_small_diff_passes_through_untouched():
    diff = "diff --git a/x b/x\n+small change"
    assert sensor.cap_diff(diff, "x | 1 +") == diff


def test_oversized_diff_is_truncated_with_stat_header():
    stat = "big_file.py | 99999 +++++"
    diff = "x" * (sensor.MAX_DIFF_CHARS + 10_000)
    capped = sensor.cap_diff(diff, stat)
    assert len(capped) < len(diff)
    assert capped.startswith(stat)
    assert "truncated" in capped
    assert str(sensor.MAX_DIFF_CHARS) in capped


def test_payload_includes_structured_commit_identity():
    payload = sensor.build_payload(
        project_name="shop-api",
        commit_hash="a" * 40,
        commit_msg="fix: apply discount",
        author="Dev <dev@example.com>",
        committed_at="2026-07-06T12:00:00+05:30",
        git_diff="diff --git a/x b/x\n+change",
        diff_stat="x | 1 +",
    )
    assert payload["project_name"] == "shop-api"
    assert payload["commit_hash"] == "a" * 40
    assert payload["author"] == "Dev <dev@example.com>"
    assert payload["committed_at"] == "2026-07-06T12:00:00+05:30"
    assert payload["git_diff"].startswith("diff --git")


def test_payload_missing_metadata_becomes_none_not_empty_string():
    payload = sensor.build_payload("p", "", "msg", "", "", "diff", "stat")
    assert payload["commit_hash"] is None
    assert payload["author"] is None
    assert payload["committed_at"] is None
