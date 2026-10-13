"""Draw every head's exact-form error from the recorded score comparison."""

import json
import math
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import BLUE, EMBER, FAINT, INK, MUTED
from figkit.svg import document
from figkit.text import Face, Outliner, run_start

HERE = Path(__file__).resolve().parent
SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


@dataclass(frozen=True)
class Geometry:
    width: float = 1280
    height: float = 430
    left: float = 80
    right: float = 1200
    top: float = 126
    bottom: float = 396


def log_x(error: float, geometry: Geometry = Geometry()) -> float:
    return geometry.left + (math.log10(error) + 8) / 11 * (geometry.right - geometry.left)


def number(value: float) -> str:
    text = f"{value:.2g}"
    if "e" not in text:
        return text
    mantissa, exponent = text.split("e")
    return f"{mantissa} × 10{str(int(exponent)).translate(SUPERSCRIPT)}"


def power_parts(value: float) -> tuple[str, str]:
    text = f"{value:.2g}"
    if "e" not in text:
        return text, ""
    mantissa, exponent = text.split("e")
    base = "10" if mantissa == "1" else f"{mantissa} × 10"
    return base, str(int(exponent)).replace("-", "−")


def power_run(out: Outliner, face: Face, parts: tuple[str, str], x: float, y: float,
              size: float, anchor: str = "start") -> str:
    base, exponent = parts
    if not exponent:
        return out.run(face, base, x, y, size, anchor)
    width = face.advance(base, size)
    start = run_start(x, width + face.advance(exponent, size * 0.7), anchor)
    return (out.run(face, base, start, y, size)
            + out.run(face, exponent, start + width, y - size * 0.4, size * 0.7))


@cache
def faces() -> dict[str, Face]:
    fonts = ROOT / "figkit" / "fonts"
    return {
        "title": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 600}),
        "body": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 430}),
        "number": Face(fonts / "MonaspaceNeonVar.ttf", {"wght": 400}),
    }


def render(data: dict, mode: str, freeze_at: float | None = None) -> str:
    geometry = Geometry()
    rows = data["rows"]
    layers = sorted({row["layer"] for row in rows})
    ys = {layer: geometry.top + index * (geometry.bottom - geometry.top) / max(1, len(layers) - 1)
          for index, layer in enumerate(layers)}
    model = data["config"]["model"].split("/")[-1]
    title = f"{len(rows)} attention heads, one score form at a time"
    subtitle = f"Relative error against {model}'s own attention scores, one prompt, every head"
    labels = (("exact", "exact form", BLUE[mode], 98),
              ("no_rope", "rotary left out", EMBER[mode], 98),
              ("plain", "plain q·k", EMBER[mode], 110))
    face, out = faces(), Outliner()
    ink = out.run(face["title"], title, 40, 44, 22)
    muted = out.run(face["body"], subtitle, 40, 70, 15)
    muted += out.run(face["body"], "Layer", 40, 116, 13)
    grid, ticks, markers, values = [], [], [], []
    for exponent in range(-8, 4):
        x = log_x(10 ** exponent, geometry)
        grid.append(f'<line x1="{x:.2f}" y1="{geometry.top}" x2="{x:.2f}" y2="{geometry.bottom}"/>')
        ticks.append(f'<line class="tick" x1="{x:.2f}" y1="{geometry.bottom}" x2="{x:.2f}" y2="{geometry.bottom + 4}"/>')
        muted += (f'<g class="power-tick">'
                  + power_run(out, face["number"], ("10", str(exponent).replace("-", "−")), x, geometry.bottom + 18, 13, "middle")
                  + '</g>')
    for index, layer in enumerate(layers):
        if index % 7 == 0 or index == len(layers) - 1:
            muted += out.run(face["number"], str(layer), 62, ys[layer] + 4, 13, "end")
    for form, label, color, y in labels:
        value = number(median(row[form] for row in rows))
        x = log_x(median(row[form] for row in rows), geometry)
        text = f"{label}, median {value}"
        values.append(text)
        prefix = f"{label}, median "
        label_ink = out.run(face["body"], prefix, x + 7, y, 13)
        label_ink += power_run(out, face["number"], power_parts(median(row[form] for row in rows)),
                               x + 7 + face["body"].advance(prefix, 13), y, 13)
        markers.append(
            f'<line class="median" x1="{x:.2f}" y1="{y + 6}" x2="{x:.2f}" y2="{geometry.bottom}" stroke="{color}" stroke-width="1"/>'
            f'<g fill="{color}">{label_ink}</g>'
        )
    dots = "".join(
        f'<circle class="head" cx="{log_x(row["exact"], geometry):.2f}" cy="{ys[row["layer"]]:.2f}" r="3.5" opacity="0.85" fill="{BLUE[mode]}"/>'
        for row in rows
    )
    body = (
        f'<g stroke="{FAINT[mode]}" stroke-width="1" opacity="0.6">{"".join(grid)}</g>'
        f'<g stroke="{MUTED[mode]}" stroke-width="1" stroke-linecap="round">'
        f'<line x1="{geometry.left}" y1="{geometry.bottom}" x2="{geometry.right}" y2="{geometry.bottom}"/>{"".join(ticks)}</g>'
        f'{"".join(markers)}{dots}<g fill="{INK[mode]}">{ink}</g><g fill="{MUTED[mode]}">{muted}</g>'
    )
    return document(
        geometry.width, geometry.height, title,
        f"{subtitle}. Each blue dot is one head at its exact-form relative error; layer {layers[0]} is at the top. "
        f"Vertical markers compare all three medians: {'; '.join(values)}.",
        "", out.defs(), body, freeze_at,
    )


if __name__ == "__main__":
    main("qk", HERE, render, json.loads((HERE / "data.json").read_text()))
