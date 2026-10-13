"""Draw completed pause cycles grouped by workload and run."""

import json
import sys
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import BLUE, INK, MUTED
from figkit.svg import document
from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Geometry:
    width: float = 1280
    height: float = 360
    left: float = 320
    right: float = 1060
    top: float = 94
    row: float = 26
    cell: float = 10
    gap: float = 2
    run_gap: float = 6


@cache
def faces() -> dict[str, Face]:
    fonts = ROOT / "figkit" / "fonts"
    return {
        "title": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 600}),
        "body": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 430}),
        "number": Face(fonts / "MonaspaceNeonVar.ttf", {"wght": 400}),
    }


def layout(runs: list[dict], index: int, geometry: Geometry) -> list[tuple[dict, float, float]]:
    x, y = geometry.left, geometry.top + index * geometry.row
    placed = []
    for run in runs:
        width = run["completed_cycles"] * (geometry.cell + geometry.gap) - geometry.gap
        if x + width > geometry.right:
            x, y = geometry.left, y + geometry.cell + geometry.gap
        placed.append((run, x, y))
        x += width + geometry.run_gap
    return placed


def footnote(data: dict) -> str:
    excluded = data["excluded"]
    kinds = Counter(run["kind"] for run in excluded)
    names = data["config"]["workload_types"] | {"paged": "managed memory"}
    counts = ", ".join(f"{count} {names[kind]}" for kind, count in kinds.items())
    gpus = ", ".join(dict.fromkeys(run["gpu"] for run in excluded))
    return (
        f"Not counted: {len(excluded)} runs on {gpus} that never paused ({counts}), "
        "listed as hazards in the gpunap README."
    )


def render(data: dict, mode: str, freeze_at: float | None = None) -> str:
    geometry = Geometry()
    rows = data["rows"]
    types = data["config"]["workload_types"]
    groups = [(kind, name, [run for run in rows if run["workload_type"] == name]) for kind, name in types.items()]
    total = sum(run["completed_cycles"] for run in rows)
    title = f"{total} pauses into host RAM, {total} bit-exact resumes"
    subtitle = f"{len(rows)} runs of {len(groups)} workload types. Each output matched an uninterrupted run."
    note = footnote(data)
    short = {
        "amp_tf": "Transformer + accumulation",
        "loader": "DataLoader workers",
        "threads": "Threads on separate streams",
    }
    face, out = faces(), Outliner()
    heading = out.run(face["title"], title, 40, 44, 22)
    muted = out.run(face["body"], subtitle, 40, 70, 15)
    muted += out.run(face["body"], note, 40, 344, 13)
    workloads, descriptions = [], []
    for index, (kind, name, runs) in enumerate(groups):
        y = geometry.top + index * geometry.row
        count = sum(run["completed_cycles"] for run in runs)
        summary = f"{count} cycles, {len(runs)} runs"
        labels = out.run(face["number"], short.get(kind, name), 40, y + 16, 13)
        labels += out.run(face["number"], summary, 1240, y + 16, 13, "end")
        marks = []
        for run, x, cell_y in layout(runs, index, geometry):
            cells = "".join(
                f'<rect class="cycle" x="{x + cycle * (geometry.cell + geometry.gap):g}" '
                f'y="{cell_y:g}" width="{geometry.cell:g}" height="{geometry.cell:g}" fill="{BLUE[mode]}"/>'
                for cycle in range(run["completed_cycles"])
            )
            marks.append(f'<g class="run" data-gpu={quoteattr(run["gpu"])} data-tag={quoteattr(run["tag"])}>{cells}</g>')
        workloads.append(
            f'<g class="workload" data-workload={quoteattr(name)}>'
            f'<g fill="{MUTED[mode]}">{labels}</g>{"".join(marks)}</g>'
        )
        descriptions.append(f"{name}: {summary}")
    body = (
        f'<g fill="{INK[mode]}">{heading}</g><g fill="{MUTED[mode]}">{muted}</g>'
        f'{"".join(workloads)}'
    )
    return document(
        geometry.width, geometry.height, title,
        f"{subtitle} One blue square per completed bit-exact pause/resume cycle; "
        f"gaps separate runs. {'; '.join(descriptions)}. {note}",
        "", out.defs(), body, freeze_at,
    )


if __name__ == "__main__":
    main("gpunap", HERE, render, json.loads((HERE / "data.json").read_text()))
