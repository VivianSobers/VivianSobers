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
from figkit.color import BLUE, EMBER, INK, MUTED
from figkit.svg import delay, document
from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Geometry:
    width: float = 1280
    left: float = 320
    right: float = 1060
    top: float = 104
    row_gap: float = 22
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


def layout(runs: list[dict], top: float, geometry: Geometry) -> list[tuple[dict, float, float]]:
    x, y = geometry.left, top
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
    heading = out.run(face["title"], title, 40, 44, 26)
    muted = out.run(face["body"], subtitle, 40, 76, 18)
    workloads, descriptions, positioned = [], [], []
    y = geometry.top
    for kind, name, runs in groups:
        placed = layout(runs, y, geometry)
        positioned.append((kind, name, runs, placed, y))
        y = max(cell_y for _, _, cell_y in placed) + geometry.cell + geometry.gap + geometry.row_gap
    positions = sorted(
        (x + cycle * (geometry.cell + geometry.gap), cell_y)
        for _, _, _, placed, _ in positioned for run, x, cell_y in placed
        for cycle in range(run["completed_cycles"])
    )
    loop = 17
    starts = [0.5 + 11.5 * index / max(total - 1, 1) for index in range(total)]
    resumes = [100 * (start + 0.4) / loop for start in starts]
    ranks = {position: index for index, position in enumerate(positions)}
    clock = delay(0, freeze_at)
    sweep = f"animation:sweep {loop}s ease-in-out infinite;{clock}"
    css = [
        "@keyframes sweep{0%{opacity:0}2.94118%{opacity:1}94.11765%{opacity:1}100%{opacity:0}}"
    ]
    for index, start in enumerate(starts):
        css.append(
            f"@keyframes pause{index}{{0%{{fill:{BLUE[mode]};opacity:0.18}}"
            f"{100 * start / loop:.5f}%{{fill:{EMBER[mode]};opacity:1}}"
            f"{resumes[index]:.5f}%{{fill:{BLUE[mode]};opacity:1}}"
            f"100%{{fill:{BLUE[mode]};opacity:1}}}}"
        )
    counters = []
    for count in range(total + 1):
        start = resumes[count - 1] if count else 0
        end = resumes[count] if count < total else 100
        keys = "0%{opacity:0}" if count else ""
        keys += f"{start:.5f}%{{opacity:1}}"
        if count < total:
            keys += f"{end:.5f}%{{opacity:0}}100%{{opacity:0}}"
        else:
            keys += "100%{opacity:1}"
        css.append(f"@keyframes count{count}{{{keys}}}")
        glyphs = out.run(face["number"], str(count), 1160, 44, 17, "end")
        counters.append(
            f'<g class="counter" data-count="{count}" opacity="{int(count == total)}" '
            f'style="animation:count{count} {loop}s steps(1,end) infinite;{clock}">{glyphs}</g>'
        )
    counter = (
        f'<g fill="{INK[mode]}" style="{sweep}">{"".join(counters)}'
        f'{out.run(face["body"], "resumed", 1240, 44, 16, "end")}</g>'
    )
    for kind, name, runs, placed, row_y in positioned:
        count = sum(run["completed_cycles"] for run in runs)
        summary = f"{count} cycles, {len(runs)} runs"
        labels = out.run(face["number"], short.get(kind, name), 40, row_y + geometry.cell, 16)
        labels += out.run(face["number"], summary, 1240, row_y + geometry.cell, 16, "end")
        marks = []
        for run, x, cell_y in placed:
            cells = []
            for cycle in range(run["completed_cycles"]):
                cell_x = x + cycle * (geometry.cell + geometry.gap)
                index = ranks[cell_x, cell_y]
                cells.append(
                    f'<rect class="cycle" x="{cell_x:g}" y="{cell_y:g}" '
                    f'width="{geometry.cell:g}" height="{geometry.cell:g}" fill="{BLUE[mode]}" '
                    f'style="animation:pause{index} {loop}s steps(1,end) infinite;{clock}"/>'
                )
            marks.append(
                f'<g class="run" data-gpu={quoteattr(run["gpu"])} data-tag={quoteattr(run["tag"])} '
                f'style="{sweep}">{"".join(cells)}</g>'
            )
        workloads.append(
            f'<g class="workload" data-workload={quoteattr(name)}>'
            f'<g fill="{MUTED[mode]}">{labels}</g>{"".join(marks)}</g>'
        )
        descriptions.append(f"{name}: {summary}")
    note_y = y + 16
    height = note_y + 20
    muted += out.run(face["body"], note, 40, note_y, 16)
    body = (
        f'<g fill="{INK[mode]}">{heading}</g><g fill="{MUTED[mode]}">{muted}</g>'
        f'{"".join(workloads)}{counter}'
    )
    return document(
        geometry.width, height, title,
        f"{subtitle} One blue square per completed bit-exact pause/resume cycle; "
        f"gaps separate runs. Cells sweep left to right, orange while paused for 0.4 seconds, "
        f"then blue on resume; the counter counts completed resumes. {'; '.join(descriptions)}. {note}",
        "".join(css), out.defs(), body, freeze_at,
    )


if __name__ == "__main__":
    main("gpunap", HERE, render, json.loads((HERE / "data.json").read_text()))
