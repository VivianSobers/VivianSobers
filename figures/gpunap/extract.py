"""Snapshot completed pause cycles from the recorded correctness runs."""

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORKLOAD_TYPES = {
    "mlp": "MLP",
    "amp_tf": "transformer with fp16 autocast and gradient accumulation",
    "cnn": "CNN with cuDNN",
    "compile": "torch.compile",
    "cudagraph": "CUDA graph replay",
    "loader": "DataLoader with worker processes",
    "threads": "two threads on separate streams",
    "hf": "Qwen3-1.7B generation",
    "nccl1": "single-GPU NCCL",
}
CONFIG = {
    "workload_types": WORKLOAD_TYPES,
    "grouping_rule": "Group by config.kind, ignoring seed, allocator, ballast, pause count and tag variants.",
    "completion_rule": {"pause_state": "checkpointed", "resume_state": "running", "event_error": "falsy"},
    "identity_rule": ["rows_identical_to_ref", "end_identical_to_ref"],
    "minimum_completed_cycles": 1,
    "skip_file_prefixes": ["fault_", "backtrace_sync_"],
    "skip_file_contains": ["bench_size"],
    "skip_file_names": ["bw.json", "pcie_link.json", "sysinfo.json"],
    "skip_top_level_error": True,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=ROOT.parent / "gpunap")
    args = parser.parse_args()
    paths, rows, excluded = ["README.md", "validation/summarize.py"], [], []
    for gpu in ("gpu1", "gpu2"):
        for path in sorted((args.repo / "validation" / f"results_{gpu}").glob("*.json")):
            if (path.name.startswith(tuple(CONFIG["skip_file_prefixes"]))
                or any(part in path.name for part in CONFIG["skip_file_contains"])
                or path.name in CONFIG["skip_file_names"]):
                continue
            paths.append(path.relative_to(args.repo).as_posix())
            run = json.loads(path.read_text())
            if "error" in run:
                continue
            completed = sum(
                not event.get("error") and event["pause"].get("state") == "checkpointed"
                and event["resume"].get("state") == "running"
                for event in run["events"]
            )
            if not completed:
                excluded.append({"tag": run["tag"], "gpu": gpu, "kind": run["config"]["kind"]})
                continue
            rows.append({
                "tag": run["tag"], "gpu": gpu,
                "driver": run["driver"]["gpu"].split(",")[1].strip(),
                "workload_type": WORKLOAD_TYPES[run["config"]["kind"]],
                "completed_cycles": completed,
                "bit_identical": run["rows_identical_to_ref"] and run["end_identical_to_ref"],
            })
    commit = subprocess.check_output(
        ["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True,
    ).strip()
    snapshot = {
        "source": {"repo": "https://github.com/VivianSobers/gpunap", "commit": commit, "paths": sorted(paths)},
        "config": CONFIG,
        "rows": rows,
        "excluded": excluded,
    }
    (HERE / "data.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Recorded {len(rows)} runs, {len({row['workload_type'] for row in rows})} workload types, "
          f"{sum(row['completed_cycles'] for row in rows)} completed cycles; "
          f"all bit-identical: {all(row['bit_identical'] for row in rows)}; source {commit}")


if __name__ == "__main__":
    main()
