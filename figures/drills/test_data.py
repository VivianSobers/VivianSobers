import json
import re
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def snapshot():
    path = HERE / "data.json"
    assert path.is_file(), "full drill run snapshot is missing"
    return json.loads(path.read_text())


def test_snapshot_keeps_five_drills_in_run_order():
    rows = snapshot()["rows"]
    assert [(row["drill"], row["alert"]) for row in rows] == [
        ("shop-api-scaled-to-zero", "ShopApiDown"),
        ("shop-api-bad-image", "KubeDeploymentRolloutStuck"),
        ("shop-api-crashloop", "KubePodCrashLooping"),
        ("app-data-disk-full", "NodeFilesystemAlmostOutOfSpace"),
        ("kubelet-stopped", "KubeNodeNotReady"),
    ]
    for row in rows:
        assert set(row) == {
            "drill", "alert", "verdict", "fired_after_s", "resolved_after_s",
            "receivers", "control_ran", "control_cleared", "started",
        }


def test_snapshot_has_passing_drills_and_held_controls():
    rows = snapshot()["rows"]
    assert len(rows) == 5
    assert all(row["verdict"] == "pass" for row in rows)
    assert all(row["control_ran"] is True for row in rows)
    assert all(row["control_cleared"] is False for row in rows)
    assert [row["receivers"] for row in rows] == [
        ["shop-team"], ["shop-team"], ["shop-team"],
        ["platform-oncall"], ["platform-oncall"],
    ]


def test_snapshot_times_match_machine_a_table_to_the_second():
    assert [
        (round(row["fired_after_s"]), round(row["resolved_after_s"]))
        for row in snapshot()["rows"]
    ] == [(105, 31), (1051, 30), (961, 331), (1846, 33), (990, 38)]


def test_snapshot_preserves_duration_precision():
    assert [
        (row["fired_after_s"], row["resolved_after_s"])
        for row in snapshot()["rows"]
    ] == [
        (105.081437657, 30.986877785),
        (1050.534667137, 30.346917613),
        (960.567843419, 330.798976279),
        (1845.947404463, 33.328483677),
        (990.487617806, 37.961333201),
    ]


def test_snapshot_selects_only_the_documented_full_run():
    data = snapshot()
    assert data["config"] == {
        "run_started": "2026-10-08T15:24:10Z",
        "run_finished": "2026-10-08T18:21:27Z",
    }
    started = [datetime.fromisoformat(row["started"]) for row in data["rows"]]
    assert started == sorted(started)
    assert all(
        datetime.fromisoformat(data["config"]["run_started"]) <= time
        < datetime.fromisoformat(data["config"]["run_finished"])
        for time in started
    )
    assert data["rows"][0]["started"] == "2026-10-08T20:54:10.398058362+05:30"
    assert data["rows"][-1]["started"] == "2026-10-08T23:06:49.059229086+05:30"


def test_snapshot_records_state_file_and_source_commit():
    source = snapshot()["source"]
    assert source["repo"] == "https://github.com/VivianSobers/drillbook"
    assert re.fullmatch(r"[0-9a-f]{40}", source["commit"])
    assert source["paths"] == [".drillbook/results.jsonl", "docs/v0.1-drill-results.md"]
