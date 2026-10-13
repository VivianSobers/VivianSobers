"""Draw the profile header from attention.json and refresh the generated block in README.md.

    .venv/bin/python header/build.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from figkit.color import CATEGORICAL, INK, MUTED, RAMP, from_oklab, hue_ramp, to_oklab
from figkit.svg import delay, document
from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent
MONA = ROOT / "figkit" / "fonts" / "MonaSansVF[wdth,opsz,wght].ttf"
NEON = ROOT / "figkit" / "fonts" / "MonaspaceNeonVar.ttf"

LATTICE_OPACITY = {"light": 0.35, "dark": 0.45}
INSET = 0.08
THRESHOLD = 0.015
START, END = "<!-- header:start -->", "<!-- header:end -->"

ROLE_TEXT = {
    "first_token": (
        "First-token head",
        ("Sends most of its attention", "to the first word"),
        "Mean weight on the first word",
    ),
    "previous_token": (
        "Previous-token head",
        ("Looks one word back",),
        "Mean weight one word back",
    ),
    "induction": (
        "Induction head",
        ("On the second reading, looks at the word", "that came next the first time"),
        "Mean weight on that word",
    ),
    "spread": (
        "Broad head",
        ("Spreads its attention over", "every earlier word"),
        "Mean normalised entropy",
    ),
}

ROLE_HUES = {"first_token": "blue", "previous_token": "aqua", "induction": "magenta", "spread": "violet"}

ROLE_ROWS = {
    "first_token": ("First-token head", "Mean weight on the first word"),
    "previous_token": ("Previous-token head", "Mean weight one word back"),
    "induction": ("Induction head", "Mean weight, over the second reading, on the word that came next the first time"),
    "spread": ("Broad head", "Mean normalised entropy of each row"),
}


@dataclass(frozen=True)
class Geometry:
    n: int
    width: float = 1280.0
    margin: float = 40.0
    aspect: float = 0.62
    top: float = 30.0

    @property
    def half_width(self) -> float:
        return (self.width - 2 * self.margin) / (2 * self.n)

    @property
    def half_height(self) -> float:
        return self.half_width * self.aspect

    @property
    def base(self) -> float:
        return self.top + (self.n + 1) * self.half_height


def cell_center(i: int, j: int, geometry: Geometry) -> tuple[float, float]:
    """Query i, key j. The diagonal runs along the bottom; distance back in the text is height."""
    return (
        geometry.margin + (i + j + 1) * geometry.half_width,
        geometry.base - (i - j + 1) * geometry.half_height,
    )


def cell_points(i: int, j: int, geometry: Geometry, inset: float) -> tuple[tuple[float, float], ...]:
    x, y = cell_center(i, j, geometry)
    w, h = geometry.half_width * (1 - inset), geometry.half_height * (1 - inset)
    return tuple((round(px, 2), round(py, 2)) for px, py in ((x, y - h), (x + w, y), (x, y + h), (x - w, y)))


@dataclass(frozen=True)
class Timing:
    scene: float = 5.5
    row: float = 0.075
    fade: float = 0.45
    scenes: int = 4

    @property
    def loop(self) -> float:
        return self.scene * self.scenes


def row_delay(scene: int, row: int, timing: Timing) -> float:
    return scene * timing.scene + row * timing.row


def update_readme(text: str, block: str) -> str:
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


@cache
def faces() -> dict[str, Face]:
    return {
        "name": Face(MONA, {"wdth": 125, "wght": 600}),
        "title": Face(MONA, {"wdth": 100, "wght": 600}),
        "body": Face(MONA, {"wdth": 100, "wght": 430}),
        "token": Face(NEON, {"wght": 400}),
    }


def _polygon(points: tuple[tuple[float, float], ...]) -> str:
    return "M" + "L".join(f"{x:g} {y:g}" for x, y in points) + "Z"


def _legend_points(x: float, y: float) -> tuple[tuple[float, float], ...]:
    w, h = 9.0, 9.0 * Geometry(n=1).aspect
    return (x, y - h), (x + w, y), (x, y + h), (x - w, y)


@cache
def scene_ramp(role: str, mode: str) -> tuple[str, ...]:
    stops = RAMP if role == "first_token" else hue_ramp(CATEGORICAL[ROLE_HUES[role]][mode])
    return stops if mode == "light" else stops[::-1]


def scene_color(t: float, stops: tuple[str, ...]) -> str:
    position = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    k = min(int(position), len(stops) - 2)
    fraction = position - k
    if fraction in (0.0, 1.0):
        return stops[k + int(fraction)]
    lo, hi = to_oklab(stops[k]), to_oklab(stops[k + 1])
    return from_oklab(*(p + (q - p) * fraction for p, q in zip(lo, hi)))


def render(data: dict, mode: str, freeze_at: float | None = None) -> str:
    """freeze_at pauses every animation at that many seconds, for previews."""
    tokens = [token.strip() for token in data["config"]["tokens"]]
    heads = data["heads"]
    geometry = Geometry(n=len(tokens))
    timing = Timing(scenes=len(heads))
    height = math.ceil(geometry.base + 40)
    right = geometry.width - geometry.margin
    face = faces()
    out = Outliner()

    token_marks = "".join(
        out.run(face["token"], token, cell_center(k, k, geometry)[0], geometry.base + 26, 16, "middle")
        for k, token in enumerate(tokens)
    )
    lattice = "".join(
        _polygon(cell_points(i, j, geometry, INSET)) for i in range(geometry.n) for j in range(i + 1)
    )

    legend_y = 238
    cells, labels, head_names, legends = [], [], [], []
    for s, head in enumerate(heads):
        ramp = scene_ramp(head["role"], mode)
        for i, row in enumerate(head["pattern"]):
            marks = "".join(
                f'<path d="{_polygon(cell_points(i, j, geometry, INSET))}" fill="{scene_color(math.sqrt(w), ramp)}"/>'
                for j, w in enumerate(row[: i + 1])
                if w >= THRESHOLD
            )
            if marks:
                cells.append(f'<g class="c s{s}" style="{delay(row_delay(s, i, timing), freeze_at)}">{marks}</g>')
        role, meaning, measure = ROLE_TEXT[head["role"]]
        head_x = geometry.margin if s % 2 == 0 else geometry.margin + 138
        head_y = 134 if s < 2 else 160
        small_name = out.run(face["body"], role, head_x + 12, head_y, 16)
        head_names.append(
            f'<g aria-label="{role}" fill="{MUTED[mode]}">{small_name}'
            f'<g class="l s{s}" fill="{INK[mode]}" style="{delay(s * timing.scene, freeze_at)}">'
            f'<path d="{_polygon(((head_x + 5, head_y - 10), (head_x + 9, head_y - 6), (head_x + 5, head_y - 2), (head_x + 1, head_y - 6)))}" '
            f'fill="{CATEGORICAL[ROLE_HUES[head["role"]]][mode]}"/>{small_name}</g></g>'
        )
        ink = out.run(face["title"], role, right, 66, 22, "end")
        ink += out.run(face["body"], f"Layer {head['layer']}, head {head['head']}", right, 93, 16, "end")
        muted = "".join(
            out.run(face["body"], line, right, 122 + 24 * k, 16, "end") for k, line in enumerate(meaning)
        )
        muted += out.run(face["body"], f"{measure}: {head['score']:.2f}", right, 126 + 24 * len(meaning), 16, "end")
        labels.append(
            f'<g class="l s{s}" style="{delay(s * timing.scene, freeze_at)}">'
            f'<g fill="{INK[mode]}">{ink}</g><g fill="{MUTED[mode]}">{muted}</g></g>'
        )

        swatches = "".join(
            f'<path d="{_polygon(_legend_points(right - 8 - 20 * (6 - k), legend_y))}" fill="{color}"/>'
            for k, color in enumerate(ramp)
        )
        legends.append(
            f'<g class="legend"><g class="l s{s}" style="{delay(s * timing.scene, freeze_at)}">'
            f'{swatches}</g></g>'
        )

    legend_text = out.run(face["body"], "Attention weight", right, legend_y - 18, 16, "end")
    for k, label in ((0, "0"), (3, "0.25"), (6, "1")):
        legend_text += out.run(face["body"], label, right - 8 - 20 * (6 - k), legend_y + 26, 16, "middle")

    name = out.run(face["name"], "Vivian Sobers", geometry.margin, 72, 44, "start")
    caption = out.run(face["body"], "Qwen3-0.6B reading the line below, twice", geometry.margin, 104, 18, "start")

    fade = 100 * timing.fade / timing.loop
    hold = 100 * timing.scene / timing.loop
    static = next(s for s, head in enumerate(heads) if head["role"] == "induction")
    # Where animation does not run, base styles leave the induction scene showing; backwards fill hides it during delays.
    css = (
        f"@keyframes on{{0%{{opacity:0}}{fade:.3f}%{{opacity:1}}{hold:.3f}%{{opacity:1}}"
        f"{hold + fade:.3f}%{{opacity:0}}100%{{opacity:0}}}}"
        f".c,.l{{opacity:0;animation:on {timing.loop:g}s ease-in-out infinite backwards}}.s{static}{{opacity:1}}"
    )
    sentence = data["config"]["sentence"].strip()
    body = (
        f'<path d="{lattice}" fill="{RAMP[0] if mode == "light" else RAMP[-1]}" opacity="{LATTICE_OPACITY[mode]}"/>'
        f"<g>{''.join(cells)}</g>"
        f'<g fill="{MUTED[mode]}">{token_marks}{caption}{legend_text}</g>'
        f'<g fill="{INK[mode]}">{name}</g>'
        f'<g class="head-names">{"".join(head_names)}</g>'
        f"<g>{''.join(labels)}</g>{''.join(legends)}"
    )
    return document(
        geometry.width, height, "Vivian Sobers",
        f'Attention patterns from four heads of Qwen3-0.6B reading "{sentence}" twice, '
        "drawn as a triangle of cells above the line.",
        css, out.defs(), body, freeze_at,
    )


def readme_block(data: dict) -> str:
    config = data["config"]
    rows = []
    for head in data["heads"]:
        ranked = sorted(
            ((value, layer, k) for layer, row in enumerate(data["scores"][head["role"]]) for k, value in enumerate(row)),
            reverse=True,
        )
        runners = [
            f"layer {layer}, head {k} ({value:.2f})"
            for value, layer, k in ranked
            if (layer, k) != (head["layer"], head["head"])
        ][:2]
        name, scored_by = ROLE_ROWS[head["role"]]
        rows.append(
            f"| {name} | {scored_by} | layer {head['layer']}, head {head['head']} | "
            f"{head['score']:.2f} | {'; '.join(runners)} |"
        )
    return "\n".join(
        [
            "<details>",
            "<summary>How the header was made</summary>",
            "",
            f"{config['model']} at revision `{config['revision'][:7]}` read the line twice, "
            f"{len(config['token_ids'])} tokens in all, in {config['dtype']} on the {config['device'].upper()} "
            f"with {config['attn_implementation']} attention and seed {config['seed']}. "
            f"I scored all {config['layers'] * config['heads_per_layer']} heads on four behaviours. "
            "The header shows the best head for each, and no head is shown for two behaviours.",
            "",
            "| Head | Scored by | Shown | Score | Next best |",
            "|:--|:--|:--|--:|:--|",
            *rows,
            "",
            "[`header/attention.json`](header/attention.json) has every head's scores and the full configuration. "
            "[`header/extract.py`](header/extract.py) regenerates it on any machine with the model cached, "
            "and [`header/build.py`](header/build.py) redraws the header from it.",
            "",
            "</details>",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", help="comma-separated frame times in seconds")
    args = parser.parse_args()
    data = json.loads((HERE / "attention.json").read_text())
    if args.preview is not None:
        try:
            times = [float(value) for value in args.preview.split(",")]
            if any(not math.isfinite(time) or time < 0 for time in times):
                raise ValueError
        except ValueError:
            parser.error("preview times must be finite, non-negative seconds")
        preview = ROOT / ".preview"
        preview.mkdir(exist_ok=True)
        for mode in ("light", "dark"):
            for time in times:
                (preview / f"heads-{mode}-{time:g}.svg").write_text(render(data, mode, freeze_at=time))
        return
    for mode in ("light", "dark"):
        (HERE / f"heads-{mode}.svg").write_text(render(data, mode))
    readme = HERE.parent / "README.md"
    readme.write_text(update_readme(readme.read_text(), readme_block(data)))


if __name__ == "__main__":
    main()
