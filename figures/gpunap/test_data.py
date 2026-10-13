import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def snapshot():
    path = HERE / "data.json"
    assert path.is_file(), "completed pause cycle snapshot is missing"
    return json.loads(path.read_text())


def test_snapshot_has_33_completed_runs_and_388_cycles():
    rows = snapshot()["rows"]
    assert len(rows) == 33
    assert sum(row["completed_cycles"] for row in rows) == 388
    assert all(type(row["completed_cycles"]) is int and row["completed_cycles"] > 0 for row in rows)
    assert len({(row["gpu"], row["tag"]) for row in rows}) == 33
    assert Counter(row["gpu"] for row in rows) == {"gpu1": 23, "gpu2": 10}


def test_snapshot_groups_variants_into_nine_readme_workloads():
    data = snapshot()
    counts = Counter()
    runs = Counter()
    for row in data["rows"]:
        counts[row["workload_type"]] += row["completed_cycles"]
        runs[row["workload_type"]] += 1
    assert dict(counts) == {
        "MLP": 106, "transformer with fp16 autocast and gradient accumulation": 86,
        "CNN with cuDNN": 41, "torch.compile": 40, "CUDA graph replay": 25,
        "DataLoader with worker processes": 41, "two threads on separate streams": 28,
        "Qwen3-1.7B generation": 11, "single-GPU NCCL": 10,
    }
    assert dict(runs) == {
        "MLP": 8, "transformer with fp16 autocast and gradient accumulation": 6,
        "CNN with cuDNN": 3, "torch.compile": 3, "CUDA graph replay": 3,
        "DataLoader with worker processes": 3, "two threads on separate streams": 3,
        "Qwen3-1.7B generation": 2, "single-GPU NCCL": 2,
    }
    assert set(counts) == set(data["config"]["workload_types"].values())
    assert "config.kind" in data["config"]["grouping_rule"]


def test_snapshot_preserves_identity_and_counts_only_completed_events():
    rows = snapshot()["rows"]
    assert all(row["bit_identical"] is True for row in rows)
    assert all(set(row) == {"tag", "gpu", "workload_type", "completed_cycles", "bit_identical", "driver"} for row in rows)
    by_run = {(row["gpu"], row["tag"]): row for row in rows}
    assert by_run["gpu1", "compile_p20_s0"]["completed_cycles"] == 19
    assert by_run["gpu1", "mlp_mallocasync_p20"]["completed_cycles"] == 15
    assert by_run["gpu2", "cudagraph_p20_s0"]["completed_cycles"] == 6
    assert by_run["gpu1", "smoke_mlp"]["completed_cycles"] == 2
    assert all(row["gpu"] == "gpu2" for row in rows if row["workload_type"] == "single-GPU NCCL")


def test_snapshot_records_exclusion_and_completion_rules():
    config = snapshot()["config"]
    assert config["completion_rule"] == {
        "pause_state": "checkpointed", "resume_state": "running", "event_error": "falsy",
    }
    assert config["identity_rule"] == ["rows_identical_to_ref", "end_identical_to_ref"]
    assert config["minimum_completed_cycles"] == 1
    assert config["skip_file_prefixes"] == ["fault_", "backtrace_sync_"]
    assert config["skip_file_contains"] == ["bench_size"]
    assert config["skip_file_names"] == ["bw.json", "pcie_link.json", "sysinfo.json"]
    assert config["skip_top_level_error"] is True


def test_snapshot_records_source_files_and_commit():
    source = snapshot()["source"]
    assert source["repo"] == "https://github.com/VivianSobers/gpunap"
    assert re.fullmatch(r"[0-9a-f]{40}", source["commit"])
    paths = source["paths"]
    assert paths == sorted(set(paths))
    assert "README.md" in paths and "validation/summarize.py" in paths
    results = [path for path in paths if path.endswith(".json")]
    assert len(results) == 38
    assert all(path.startswith(("validation/results_gpu1/", "validation/results_gpu2/")) for path in results)


def test_runs_that_never_paused_are_kept_aside():
    data = json.loads((Path(__file__).resolve().parent / "data.json").read_text())
    assert len(data["excluded"]) == 5
    assert {run["gpu"] for run in data["excluded"]} == {"gpu1"}
    assert not {(run["gpu"], run["tag"]) for run in data["excluded"]} & {(run["gpu"], run["tag"]) for run in data["rows"]}


def test_each_run_records_its_full_driver_version():
    versions = {"gpu1": "595.84", "gpu2": "580.178.04"}
    assert all(row["driver"] == versions[row["gpu"]] for row in snapshot()["rows"])
