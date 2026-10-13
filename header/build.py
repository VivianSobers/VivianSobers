"""Draw the profile header from attention.json and refresh the generated block in README.md.

    .venv/bin/python header/build.py
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent
MONA = ROOT / "figkit" / "fonts" / "MonaSansVF[wdth,opsz,wght].ttf"
NEON = ROOT / "figkit" / "fonts" / "MonaspaceNeonVar.ttf"

# The sequential blue that marks Qwen3-0.6B in the qk-attribution figures, light to dark.
RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
INK = {"light": "#1f2328", "dark": "#f0f6fc"}
MUTED = {"light": "#59636e", "dark": "#9198a1"}
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


def _to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _from_linear(channel: float) -> float:
    channel = min(max(channel, 0.0), 1.0)
    return 12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055


def to_oklab(hex_color: str) -> tuple[float, float, float]:
    r, g, b = (_to_linear(int(hex_color[k : k + 2], 16) / 255) for k in (1, 3, 5))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def from_oklab(lightness: float, a: float, b: float) -> str:
    l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    return "#" + "".join(f"{round(_from_linear(c) * 255):02x}" for c in rgb)


def oklab_lightness(hex_color: str) -> float:
    return to_oklab(hex_color)[0]


def ramp_color(t: float, mode: str) -> str:
    """t = 0 is no attention and recedes toward the page; t = 1 is full attention."""
    stops = RAMP if mode == "light" else RAMP[::-1]
    position = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    k = min(int(position), len(stops) - 2)
    fraction = position - k
    if fraction in (0.0, 1.0):
        return stops[k + int(fraction)]
    lo, hi = to_oklab(stops[k]), to_oklab(stops[k + 1])
    return from_oklab(*(p + (q - p) * fraction for p, q in zip(lo, hi)))


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


def _delay(seconds: float, freeze_at: float | None) -> str:
    return f"animation-delay:{seconds - (freeze_at or 0.0):.3f}s"


def _legend_points(x: float, y: float) -> tuple[tuple[float, float], ...]:
    w, h = 9.0, 9.0 * Geometry(n=1).aspect
    return (x, y - h), (x + w, y), (x, y + h), (x - w, y)


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
        out.run(face["token"], token, cell_center(k, k, geometry)[0], geometry.base + 24, 15, "middle")
        for k, token in enumerate(tokens)
    )
    lattice = "".join(
        _polygon(cell_points(i, j, geometry, INSET)) for i in range(geometry.n) for j in range(i + 1)
    )

    cells, labels = [], []
    for s, head in enumerate(heads):
        for i, row in enumerate(head["pattern"]):
            marks = "".join(
                f'<path d="{_polygon(cell_points(i, j, geometry, INSET))}" fill="{ramp_color(math.sqrt(w), mode)}"/>'
                for j, w in enumerate(row[: i + 1])
                if w >= THRESHOLD
            )
            if marks:
                cells.append(f'<g class="c s{s}" style="{_delay(row_delay(s, i, timing), freeze_at)}">{marks}</g>')
        role, meaning, measure = ROLE_TEXT[head["role"]]
        ink = out.run(face["title"], role, right, 66, 22, "end")
        ink += out.run(face["body"], f"Layer {head['layer']}, head {head['head']}", right, 93, 16, "end")
        muted = "".join(
            out.run(face["body"], line, right, 122 + 22 * k, 15, "end") for k, line in enumerate(meaning)
        )
        muted += out.run(face["body"], f"{measure}: {head['score']:.2f}", right, 130 + 22 * len(meaning), 15, "end")
        labels.append(
            f'<g class="l s{s}" style="{_delay(s * timing.scene, freeze_at)}">'
            f'<g fill="{INK[mode]}">{ink}</g><g fill="{MUTED[mode]}">{muted}</g></g>'
        )

    legend_y = 238
    swatches = "".join(
        f'<path d="{_polygon(_legend_points(right - 8 - 20 * (6 - k), legend_y))}" fill="{ramp_color(k / 6, mode)}"/>'
        for k in range(7)
    )
    legend_text = out.run(face["body"], "Attention weight", right, legend_y - 16, 13, "end")
    for k, label in ((0, "0"), (3, "0.25"), (6, "1")):
        legend_text += out.run(face["body"], label, right - 8 - 20 * (6 - k), legend_y + 22, 12, "middle")

    name = out.run(face["name"], "Vivian Sobers", geometry.margin, 72, 44, "start")
    caption = out.run(face["body"], "Qwen3-0.6B reading the line below, twice", geometry.margin, 102, 15, "start")

    fade = 100 * timing.fade / timing.loop
    hold = 100 * timing.scene / timing.loop
    static = next(s for s, head in enumerate(heads) if head["role"] == "induction")
    # Where animation does not run, base styles leave the induction scene showing; backwards fill hides it during delays.
    css = (
        f"@keyframes on{{0%{{opacity:0}}{fade:.3f}%{{opacity:1}}{hold:.3f}%{{opacity:1}}"
        f"{hold + fade:.3f}%{{opacity:0}}100%{{opacity:0}}}}"
        f".c,.l{{opacity:0;animation:on {timing.loop:g}s ease-in-out infinite backwards}}.s{static}{{opacity:1}}"
        + (".c,.l{animation-play-state:paused}" if freeze_at is not None else "")
        + "@media (prefers-reduced-motion:reduce){.c,.l{animation:none}}"
    )
    sentence = data["config"]["sentence"].strip()
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {geometry.width:g} {height}" '
        f'width="{geometry.width:g}" height="{height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">Vivian Sobers</title>'
        f'<desc id="desc">Attention patterns from four heads of Qwen3-0.6B reading "{sentence}" twice, '
        f"drawn as a triangle of cells above the line.</desc>"
        f"<style>{css}</style><defs>{out.defs()}</defs>"
        f'<path d="{lattice}" fill="{RAMP[0] if mode == "light" else RAMP[-1]}" opacity="{LATTICE_OPACITY[mode]}"/>'
        f"<g>{''.join(cells)}</g>"
        f'<g fill="{MUTED[mode]}">{token_marks}{caption}{legend_text}</g>'
        f'<g fill="{INK[mode]}">{name}</g>'
        f"<g>{''.join(labels)}</g><g>{swatches}</g>"
        "</svg>\n"
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
    data = json.loads((HERE / "attention.json").read_text())
    for mode in ("light", "dark"):
        (HERE / f"heads-{mode}.svg").write_text(render(data, mode))
    readme = HERE.parent / "README.md"
    readme.write_text(update_readme(readme.read_text(), readme_block(data)))


if __name__ == "__main__":
    main()
