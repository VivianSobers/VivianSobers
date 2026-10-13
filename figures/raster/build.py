"""Draw the recorded target, fitted triangle scene, and loss curve."""

import base64
import json
import math
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import BLUE, FAINT, INK, MUTED, linear_to_srgb_hex
from figkit.svg import delay, document
from figkit.text import Face, Outliner, power_run

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float


def panel_point(vertex, box: Box) -> tuple[float, float]:
    return box.x + vertex[0] * box.width, box.y + vertex[1] * box.height


def loss_point(step: float, loss: float, data: dict, box: Box) -> tuple[float, float]:
    low = min(data["best_loss"], *(point["loss"] for point in data["loss"]))
    low = 10 ** math.floor(math.log10(low))
    high = max(data["first_loss"], *(point["loss"] for point in data["loss"]))
    fraction = (math.log(high) - math.log(loss)) / (math.log(high) - math.log(low))
    return box.x + step / (data["steps"] - 1) * box.width, box.y + fraction * box.height


def rgb(channels) -> str:
    return linear_to_srgb_hex(channels)


def rect(box: Box) -> str:
    return f'x="{box.x:g}" y="{box.y:g}" width="{box.width:g}" height="{box.height:g}"'


def reveal_time(fraction: float) -> float:
    """Invert the curve's ease-in-out progress to time a paint-order reveal."""
    low, high = 0.0, 1.0
    for _ in range(40):
        t = (low + high) / 2
        if 3 * t * t - 2 * t ** 3 < fraction:
            low = t
        else:
            high = t
    t = (low + high) / 2
    return 8 * (3 * (1 - t) ** 2 * t * 0.42 + 3 * (1 - t) * t * t * 0.58 + t ** 3)


def reveal_frames(name: str, fraction: float) -> str:
    return (
        f"@keyframes {name}{{0%{{opacity:0;animation-timing-function:steps(1,end)}}"
        f"{100 * reveal_time(fraction) / 15:.6f}%{{opacity:1}}"
        "93.333333%{opacity:1;animation-timing-function:ease-in-out}100%{opacity:0}}"
    )


@cache
def faces() -> dict[str, Face]:
    fonts = ROOT / "figkit" / "fonts"
    return {
        "title": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 600}),
        "body": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 430}),
        "number": Face(fonts / "MonaspaceNeonVar.ttf", {"wght": 400}),
    }


def render(data: dict, mode: str, freeze_at: float | None = None) -> str:
    target, scene, chart = Box(40, 126, 300, 300), Box(410, 126, 300, 300), Box(848, 156, 392, 226)
    face, out = faces(), Outliner()
    count = len(data["triangles"])
    title = f"An image, rebuilt from {count} triangles by gradient descent"
    cores = data["config"]["cpu_cores"]
    core_label = "one CPU core" if cores == 1 else f"{cores} CPU cores"
    subtitle = f"Soft rasterization in Rust, seed {data['config']['seed']}, {data['steps']} steps on {core_label}."
    ratio = f"loss fell {data['first_loss'] / data['best_loss']:.0f}× (best at step {data['best_iter']})"
    heading = out.run(face["title"], title, 40, 44, 22)
    labels = out.run(face["body"], subtitle, 40, 70, 15)
    for label, x in (("Target image", target.x), ("Fitted triangles", scene.x), ("Loss (log scale)", 790)):
        labels += out.run(face["body"], label, x, 110, 15)
    ratio_text = out.run(face["number"], ratio, 790, 133, 13)
    png = base64.b64encode((HERE / "target.png").read_bytes()).decode("ascii")
    triangles, frames = [], []
    for i, triangle in enumerate(data["triangles"]):
        points = " ".join(f"{x:.3f},{y:.3f}" for x, y in (panel_point(vertex, scene) for vertex in triangle["verts"]))
        triangles.append(
            f'<polygon class="triangle" points="{points}" fill="{rgb(triangle["color"])}" '
            f'fill-opacity="{triangle["alpha"]:g}" '
            f'style="animation-name:triangle{i};{delay(0, freeze_at)}"/>'
        )
        frames.append(reveal_frames(f"triangle{i}", (i + 1) / count))
    best = {"iter": data["best_iter"], "loss": data["best_loss"]}
    series = sorted([point for point in data["loss"] if point["iter"] != best["iter"]] + [best], key=lambda point: point["iter"])
    points = " ".join(
        f"{x:.3f},{y:.3f}" for x, y in (loss_point(point["iter"], point["loss"], data, chart) for point in series)
    )
    best_x, best_y = loss_point(best["iter"], best["loss"], data, chart)
    low, high = min(point["loss"] for point in series), max(point["loss"] for point in series)
    grid = []
    for exponent in range(math.floor(math.log10(low)), math.floor(math.log10(high)) + 1):
        value = 10 ** exponent
        _, y = loss_point(0, value, data, chart)
        grid.append(
            f'<line x1="{chart.x:g}" x2="{chart.x + chart.width:g}" y1="{y:.3f}" y2="{y:.3f}" '
            f'stroke="{FAINT[mode]}" stroke-width="1"/>'
        )
        labels += (f'<g class="loss-tick" data-exponent="{exponent}" data-y="{y:.6f}">'
                   + power_run(out, face["number"], ("10", str(exponent).replace("-", "−")),
                               chart.x - 12, y + 4, 13, "end") + '</g>')
    last = data["steps"] - 1
    for step in sorted(set(range(0, last + 1, 200)) | {last}):
        x, _ = loss_point(step, low, data, chart)
        grid.append(
            f'<line x1="{x:.3f}" x2="{x:.3f}" y1="{chart.y + chart.height:g}" '
            f'y2="{chart.y + chart.height + 5:g}" stroke="{FAINT[mode]}" stroke-width="1"/>'
        )
        labels += (f'<g class="step-tick" data-step="{step}">'
                   + out.run(face["number"], str(step), x, 405, 13, "middle") + '</g>')
    labels += out.run(face["body"], "Step", chart.x + chart.width / 2, 426, 13, "middle")
    labels += out.run(face["body"], f"Drawn in paint order; the fitter moves all {count} at once.", scene.x, 448, 13)
    clip = f'<clipPath id="scene-box" clipPathUnits="userSpaceOnUse"><rect {rect(scene)}/></clipPath>'
    clip += (
        '<clipPath id="loss-box" clipPathUnits="userSpaceOnUse">'
        f'<rect class="loss-reveal" {rect(Box(chart.x, chart.y - 5, chart.width + 2, chart.height + 10))} '
        f'style="{delay(0, freeze_at)}"/></clipPath>'
    )
    frames.append(reveal_frames("show-best", data["best_iter"] / (data["steps"] - 1)))
    css = (
        "".join(frames)
        + ".triangle{opacity:1;animation-duration:15s;animation-iteration-count:infinite}"
        + "@keyframes draw-loss{0%{transform:scaleX(0);animation-timing-function:ease-in-out}"
        "53.333333%,100%{transform:scaleX(1)}}"
        f".loss-reveal{{transform:scaleX(1);transform-origin:{chart.x:g}px 0;animation:draw-loss 15s linear infinite}}"
        ".best{opacity:1;animation:show-best 15s linear infinite}"
        "@keyframes fade-loss{0%,93.333333%{opacity:1}100%{opacity:0}}"
        ".loss-motion{opacity:1;animation:fade-loss 15s ease-in-out infinite}"
    )
    body = (
        f'<g fill="{INK[mode]}">{heading}</g><g fill="{MUTED[mode]}">{labels}</g>'
        f'<g fill="{BLUE[mode]}">{ratio_text}</g>'
        f'<image {rect(target)} href="data:image/png;base64,{png}"/>'
        f'<g class="scene" clip-path="url(#scene-box)"><rect {rect(scene)} fill="{rgb(data["background"])}"/>'
        f'{"".join(triangles)}</g>'
        f'<g fill="none" stroke="{FAINT[mode]}" stroke-width="1">'
        f'<rect {rect(target)}/><rect {rect(scene)}/></g>'
        f'<g stroke-linecap="round">{"".join(grid)}'
        f'<g class="loss-motion" style="{delay(0, freeze_at)}">'
        f'<polyline class="loss" points="{points}" fill="none" stroke="{BLUE[mode]}" stroke-width="2" '
        'clip-path="url(#loss-box)"/>'
        f'<circle class="best" cx="{best_x:.3f}" cy="{best_y:.3f}" r="4" fill="{BLUE[mode]}" '
        f'style="{delay(0, freeze_at)}"/></g></g>'
    )
    return document(
        1280, 460, title,
        f"{subtitle} Left: the {data['target']['width']} by {data['target']['height']} px target. "
        f"Middle: {count} translucent triangles in paint order on the fitted background. "
        f"Right: recorded loss on a logarithmic scale; {ratio}. "
        f"First loss {data['first_loss']:.9g}, best loss {data['best_loss']:.9g}, last loss {data['last_loss']:.9g}. "
        "The blue dot marks the best scene's step. Triangles appear in paint order over eight seconds "
        "as the loss curve is revealed; the complete scene holds for six seconds, then fades for one second. "
        "The assembly reveals the recorded best scene, rather than intermediate optimization scenes.",
        css, out.defs() + clip, body, freeze_at,
    )


if __name__ == "__main__":
    main("raster", HERE, render, json.loads((HERE / "data.json").read_text()))
