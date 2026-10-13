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
from figkit.svg import delay, document
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
            f'<g class="label {form}" opacity="1" fill="{color}" style="{delay(0, freeze_at)}">{label_ink}</g>'
        )
    traces, dots = [], []
    for row in rows:
        y = ys[row["layer"]]
        stagger = delay(row["layer"] * 0.02, freeze_at)
        for form in ("plain", "no_rope"):
            paint = (f'fill="none" stroke="{EMBER[mode]}" stroke-width="1"' if form == "plain"
                     else f'fill="{EMBER[mode]}"')
            traces.append(
                f'<circle class="trace {form}" cx="{log_x(row[form], geometry):.2f}" cy="{y:.2f}" '
                f'r="2.5" opacity="0.3" {paint} style="{stagger}"/>'
            )
        x = log_x(row["exact"], geometry)
        stops = f'--plain:{log_x(row["plain"], geometry) - x:.2f}px;--no_rope:{log_x(row["no_rope"], geometry) - x:.2f}px'
        dots.append(
            f'<circle class="head" cx="{x:.2f}" cy="{y:.2f}" r="3.5" opacity="0.85" '
            f'fill="{BLUE[mode]}" style="{stops};{stagger}"/>'
        )
    css = (
        "@keyframes travel{0%,12.5%{transform:translateX(var(--plain))}"
        "21.875%,34.375%{transform:translateX(var(--no_rope))}"
        "43.75%,93.75%{transform:translateX(0)}93.751%,100%{transform:translateX(var(--plain))}}"
        f"@keyframes paint{{0%,34.375%{{fill:{EMBER[mode]};opacity:0.85}}"
        f"43.75%,87.5%{{fill:{BLUE[mode]};opacity:0.85}}93.75%{{fill:{BLUE[mode]};opacity:0}}"
        f"93.751%{{fill:{EMBER[mode]};opacity:0}}100%{{fill:{EMBER[mode]};opacity:0.85}}}}"
        ".head{animation:travel 16s ease-in-out infinite backwards,paint 16s ease-in-out infinite backwards}"
        "@keyframes trail_plain{0%,12.5%{opacity:0}21.875%,87.5%{opacity:0.3}93.75%,100%{opacity:0}}"
        "@keyframes trail_no_rope{0%,34.375%{opacity:0}43.75%,87.5%{opacity:0.3}93.75%,100%{opacity:0}}"
        ".trace.plain{animation:trail_plain 16s ease-in-out infinite backwards}"
        ".trace.no_rope{animation:trail_no_rope 16s ease-in-out infinite backwards}"
        "@keyframes label_plain{0%,12.5%,100%{opacity:1}21.875%,87.5%{opacity:0.4}}"
        "@keyframes label_no_rope{0%,12.5%,43.75%,100%{opacity:0.4}21.875%,34.375%{opacity:1}}"
        "@keyframes label_exact{0%,34.375%,100%{opacity:0.4}43.75%,87.5%{opacity:1}}"
        ".label.plain{animation:label_plain 16s ease-in-out infinite backwards}"
        ".label.no_rope{animation:label_no_rope 16s ease-in-out infinite backwards}"
        ".label.exact{animation:label_exact 16s ease-in-out infinite backwards}"
    )
    body = (
        f'<g stroke="{FAINT[mode]}" stroke-width="1" opacity="0.6">{"".join(grid)}</g>'
        f'<g stroke="{MUTED[mode]}" stroke-width="1" stroke-linecap="round">'
        f'<line x1="{geometry.left}" y1="{geometry.bottom}" x2="{geometry.right}" y2="{geometry.bottom}"/>{"".join(ticks)}</g>'
        f'{"".join(markers)}{"".join(traces)}{"".join(dots)}<g fill="{INK[mode]}">{ink}</g><g fill="{MUTED[mode]}">{muted}</g>'
    )
    return document(
        geometry.width, geometry.height, title,
        f"{subtitle}. Each blue dot is one head at its exact-form relative error; layer {layers[0]} is at the top. "
        "Faint orange dots mark the earlier plain-product and rotary-left-out forms. "
        "Plain-product traces are open rings; rotary-left-out traces are filled. "
        "Filled heads slide through the three forms, turning blue at the exact form. "
        f"Vertical markers compare all three medians: {'; '.join(values)}.",
        css, out.defs(), body, freeze_at,
    )


if __name__ == "__main__":
    main("qk", HERE, render, json.loads((HERE / "data.json").read_text()))
