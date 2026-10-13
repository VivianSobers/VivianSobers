"""Draw the recorded drills and their control runs on one clock."""

import json
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import BLUE, EMBER, FAINT, INK, MUTED
from figkit.svg import delay, document
from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Geometry:
    width: float = 1280
    height: float = 420
    left: float = 350
    right: float = 1240
    top: float = 122
    bottom: float = 354
    axis: float = 392
    minutes: float = 36


def time_x(minutes: float, geometry: Geometry = Geometry()) -> float:
    return geometry.left + minutes / geometry.minutes * (geometry.right - geometry.left)


def duration(seconds: float) -> str:
    minutes, seconds = divmod(round(seconds), 60)
    return f"{minutes}m{seconds:02d}s" if minutes else f"{seconds}s"


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
    face, out = faces(), Outliner()
    count = ("Zero", "One", "Two", "Three", "Four", "Five")[len(rows)]
    title = f"{count} drills, each checked against a control run"
    date = data["config"]["run_started"].split("T")[0]
    subtitle = f"One drillbook run on {date}. Minutes after the fault was injected."
    heading = out.run(face["title"], title, 40, 44, 22)
    subline = out.run(face["body"], subtitle, 40, 70, 15)
    ticks, lanes, descriptions = [], [], []
    sweep, hold, fade = 12, 4, 1
    loop = sweep + hold + fade
    stop, fade_start = 100 * sweep / loop, 100 * (sweep + hold) / loop
    span = geometry.right - geometry.left
    frozen = delay(0, freeze_at)
    css = (
        f"@keyframes sweep{{0%{{transform:translateX(0)}}{stop:.6f}%,100%{{transform:translateX({span:g}px)}}}}"
        f"@keyframes uncover{{0%{{width:0}}{stop:.6f}%,100%{{width:{span:g}px}}}}"
        f"@keyframes fade{{0%,{fade_start:.6f}%{{opacity:1}}100%{{opacity:0}}}}"
        f".playhead{{transform:translateX({span:g}px)}}"
        f".playhead{{animation:sweep {loop:g}s linear infinite}}"
        f".clock-window{{animation:uncover {loop:g}s linear infinite}}"
        f".clock-marks{{animation:fade {loop:g}s ease-in-out infinite}}"
        ".fired,.cleared,.fired-label,.cleared-label,.control-label{opacity:1}"
    )
    clip = (
        f'<clipPath id="clock-window" clipPathUnits="userSpaceOnUse">'
        f'<rect class="clock-window" x="{geometry.left:g}" y="{geometry.top - 30:g}" '
        f'width="{span:g}" height="{geometry.axis - geometry.top + 30:g}" style="{frozen}"/></clipPath>'
    )
    tick_minutes = range(0, int(geometry.minutes) + 1, 5)
    for minute in tick_minutes:
        x = time_x(minute, geometry)
        label = f"{minute} min" if minute == tick_minutes[-1] else str(minute)
        ticks.append(
            f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{geometry.top - 20:g}" '
            f'y2="{geometry.axis:g}" stroke="{FAINT[mode]}" stroke-width="1" opacity="0.6"/>'
            f'<g fill="{MUTED[mode]}">{out.run(face["number"], label, x, geometry.axis + 18, 13, "middle")}</g>'
        )
    for index, row in enumerate(rows):
        y = geometry.top + index * (geometry.bottom - geometry.top) / max(1, len(rows) - 1)
        fired = time_x(row["fired_after_s"] / 60, geometry)
        cleared = time_x((row["fired_after_s"] + row["resolved_after_s"]) / 60, geometry)
        styles = {}
        for kind, seconds in (("fired", row["fired_after_s"]),
                              ("cleared", row["fired_after_s"] + row["resolved_after_s"])):
            name = f"{kind}-{index}"
            arrival = 100 * sweep * seconds / (geometry.minutes * 60 * loop)
            css += f"@keyframes {name}{{0%{{opacity:0}}{arrival:.6f}%{{opacity:1}}100%{{opacity:1}}}}"
            styles[kind] = f"animation:{name} {loop:g}s steps(1,end) infinite;{frozen}"
        fired_label = f"fired {duration(row['fired_after_s'])}"
        cleared_label = f"cleared +{duration(row['resolved_after_s'])}"
        labels = out.run(face["number"], row["drill"], 40, y - 4, 13)
        labels += out.run(face["number"], row["alert"], 40, y + 16, 13)
        anchor = "end" if cleared + face["number"].advance(cleared_label, 13) > geometry.right else "start"
        control = (
            f'<line class="control" clip-path="url(#clock-window)" x1="{fired:.2f}" x2="{geometry.right:g}" '
            f'y1="{y + 10:g}" y2="{y + 10:g}" stroke="{EMBER[mode]}" '
            'stroke-width="1" stroke-dasharray="5 5"/>'
        ) if row["control_ran"] and not row["control_cleared"] else ""
        if index == 0 and control:
            control += (
                f'<g class="control-label" fill="{EMBER[mode]}" style="animation:control-label {loop:g}s steps(1,end) infinite;{frozen}">'
                f'{out.run(face["body"], "control: still firing", geometry.right, y - 14, 13, "end")}</g>'
            )
            css += f"@keyframes control-label{{0%{{opacity:0}}{stop:.6f}%{{opacity:1}}100%{{opacity:1}}}}"
        fault_label = (
            f'<g class="fault-label" fill="{EMBER[mode]}">'
            f'{out.run(face["body"], "fault", geometry.left, y - 14, 13)}</g>'
        ) if index == 0 else ""
        lanes.append(
            f'<g class="lane" data-drill={quoteattr(row["drill"])}>'
            f'<g fill="{MUTED[mode]}">{labels}</g>'
            f'<line class="baseline" x1="{geometry.left:g}" x2="{geometry.right:g}" '
            f'y1="{y:g}" y2="{y:g}" stroke="{FAINT[mode]}" stroke-width="1"/>'
            f'<line class="wait" clip-path="url(#clock-window)" x1="{geometry.left:g}" x2="{fired:.2f}" '
            f'y1="{y:g}" y2="{y:g}" stroke="{EMBER[mode]}" stroke-width="2" opacity="0.35"/>'
            f'<line class="fault" x1="{geometry.left:g}" x2="{geometry.left:g}" '
            f'y1="{y - 6:g}" y2="{y + 6:g}" stroke="{EMBER[mode]}" stroke-width="2"/>'
            f'{fault_label}'
            f'{control}<line class="firing" clip-path="url(#clock-window)" x1="{fired:.2f}" x2="{cleared:.2f}" '
            f'y1="{y:g}" y2="{y:g}" stroke="{EMBER[mode]}" stroke-width="2"/>'
            f'<circle class="fired" style="{styles["fired"]}" cx="{fired:.2f}" cy="{y:g}" r="4" fill="{EMBER[mode]}"/>'
            f'<circle class="cleared" style="{styles["cleared"]}" cx="{cleared:.2f}" cy="{y:g}" r="4" fill="{BLUE[mode]}"/>'
            f'<g class="fired-label" style="{styles["fired"]}" fill="{EMBER[mode]}">{out.run(face["number"], fired_label, fired, y - 14, 13)}</g>'
            f'<g class="cleared-label" style="{styles["cleared"]}" fill="{BLUE[mode]}">{out.run(face["number"], cleared_label, cleared, y + 23, 13, anchor)}</g></g>'
        )
        descriptions.append(f"{row['drill']} ({row['alert']}): {fired_label}, {cleared_label}")
    body = (
        f'<g fill="{INK[mode]}">{heading}</g><g fill="{MUTED[mode]}">{subline}</g>'
        f'<g stroke-linecap="round">{"".join(ticks)}'
        f'<g class="clock-marks" style="{frozen}">{"".join(lanes)}'
        f'<line class="playhead" x1="{geometry.left:g}" x2="{geometry.left:g}" '
        f'y1="{geometry.top - 20:g}" y2="{geometry.axis:g}" stroke="{MUTED[mode]}" '
        f'stroke-width="1" style="{frozen}"/></g>'
        f'<line x1="{geometry.left:g}" x2="{geometry.right:g}" y1="{geometry.axis:g}" '
        f'y2="{geometry.axis:g}" stroke="{FAINT[mode]}" stroke-width="1"/></g>'
    )
    return document(
        geometry.width, geometry.height, title,
        f"{subtitle} {'; '.join(descriptions)}. "
        "Orange ticks mark fault injection; faint orange lines show the wait before firing. "
        "Orange segments span firing to clearing; blue dots mark clearing. "
        "Dashed orange lines show the control runs still firing.",
        css, out.defs() + clip, body, freeze_at,
    )


if __name__ == "__main__":
    main("drills", HERE, render, json.loads((HERE / "data.json").read_text()))
