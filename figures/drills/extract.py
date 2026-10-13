"""Snapshot the documented full drill run from the local state file."""

import argparse
import json
import re
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULT = Path(".drillbook/results.jsonl")
DOC = Path("docs/v0.1-drill-results.md")
RUN_STARTED = "2026-10-08T15:24:10Z"
RUN_FINISHED = "2026-10-08T18:21:27Z"


def seconds(duration: str) -> float:
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(\d+(?:\.\d+)?)s", duration)
    if match is None:
        raise ValueError(f"Unsupported duration: {duration}")
    return float(sum(
        Decimal(value or "0") * scale
        for value, scale in zip(match.groups(), (3600, 60, 1))
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=ROOT.parent / "drillbook")
    args = parser.parse_args()
    start, end = (datetime.fromisoformat(time) for time in (RUN_STARTED, RUN_FINISHED))
    results = [json.loads(line) for line in (args.repo / RESULT).read_text().splitlines() if line.strip()]
    results = sorted(
        (row for row in results if start <= datetime.fromisoformat(row["started"]) < end),
        key=lambda row: datetime.fromisoformat(row["started"]),
    )
    if len(results) != 5:
        raise ValueError(f"Expected five results in the full run, found {len(results)}")
    commit = subprocess.check_output(
        ["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True,
    ).strip()
    snapshot = {
        "source": {
            "repo": "https://github.com/VivianSobers/drillbook",
            "commit": commit,
            "paths": [RESULT.as_posix(), DOC.as_posix()],
        },
        "config": {"run_started": RUN_STARTED, "run_finished": RUN_FINISHED},
        "rows": [
            {
                **{key: row[key] for key in (
                    "drill", "alert", "verdict", "receivers", "control_ran", "control_cleared", "started",
                )},
                "fired_after_s": seconds(row["fired_after"]),
                "resolved_after_s": seconds(row["resolved_after"]),
            }
            for row in results
        ],
    }
    (HERE / "data.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Recorded {len(snapshot['rows'])} drills from {commit}")


if __name__ == "__main__":
    main()
