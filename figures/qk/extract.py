"""Snapshot per-head relative score errors from the recorded experiment."""

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULT = Path("experiments/results/003-qk-form-qwen3-0.6b.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=ROOT.parent / "qk-attribution")
    args = parser.parse_args()
    data = json.loads((args.repo / RESULT).read_text())
    commit = subprocess.check_output(
        ["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True,
    ).strip()
    snapshot = {
        "source": {
            "repo": "https://github.com/VivianSobers/qk-attribution",
            "commit": commit,
            "paths": [RESULT.as_posix()],
        },
        "config": {key: data[key] for key in ("model", "prompt", "seed", "seq")},
        "rows": [
            {
                "layer": row["layer"],
                "head": row["head"],
                "plain": row["plain"]["rel_fro"],
                "no_rope": row["no_rope"]["rel_fro"],
                "exact": row["derived"]["rel_fro"],
            }
            for row in data["rows"]
        ],
    }
    (HERE / "data.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Recorded {len(snapshot['rows'])} heads from {commit}")


if __name__ == "__main__":
    main()
