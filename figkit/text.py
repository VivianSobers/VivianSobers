"""Type shaped with HarfBuzz and drawn as outlines, so the header needs no font when it is viewed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


@dataclass(frozen=True)
class PlacedGlyph:
    name: str
    x: float
    y: float


class Face:
    """One variable font pinned at one point in its design space."""

    def __init__(self, path: Path, axes: dict[str, float]):
        self._tt = TTFont(path)
        location = {axis.axisTag: axes.get(axis.axisTag, axis.defaultValue) for axis in self._tt["fvar"].axes}
        self.key = re.sub(r"[^A-Za-z0-9]", "", Path(path).stem) + "".join(
            f"{tag}{value:g}" for tag, value in sorted(location.items())
        )
        self.units_per_em = self._tt["head"].unitsPerEm
        self._glyphs = self._tt.getGlyphSet(location=location)
        self._hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self._hb.set_variations(location)

    def shape(self, text: str, size: float) -> tuple[list[PlacedGlyph], float]:
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        hb.shape(self._hb, buffer, {})
        scale = size / self.units_per_em
        glyphs, pen = [], 0
        for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
            name = self._tt.getGlyphName(info.codepoint)
            glyphs.append(PlacedGlyph(name, (pen + position.x_offset) * scale, -position.y_offset * scale))
            pen += position.x_advance
        return glyphs, pen * scale

    def advance(self, text: str, size: float) -> float:
        return self.shape(text, size)[1]

    @cache
    def outline(self, name: str) -> str:
        pen = SVGPathPen(self._glyphs, ntos=lambda value: f"{round(value)}")
        self._glyphs[name].draw(pen)
        return pen.getCommands()


def run_start(x: float, width: float, anchor: str) -> float:
    return x - {"start": 0.0, "middle": width / 2, "end": width}[anchor]


class Outliner:
    """Collects glyph outlines once and places them as <use> references."""

    def __init__(self) -> None:
        self._ids: dict[tuple[str, str], str] = {}
        self._paths: list[str] = []

    def run(self, face: Face, text: str, x: float, y: float, size: float, anchor: str = "start") -> str:
        glyphs, width = face.shape(text, size)
        start = run_start(x, width, anchor)
        scale = size / face.units_per_em
        uses = []
        for glyph in glyphs:
            commands = face.outline(glyph.name)
            if not commands:
                continue
            ref = self._ids.get((face.key, glyph.name))
            if ref is None:
                ref = self._ids[(face.key, glyph.name)] = f"g{len(self._ids)}"
                self._paths.append(f'<path id="{ref}" d="{commands}"/>')
            uses.append(
                f'<use href="#{ref}" transform="translate({start + glyph.x:.2f} {y + glyph.y:.2f}) '
                f'scale({scale:.5f} {-scale:.5f})"/>'
            )
        return "".join(uses)

    def defs(self) -> str:
        return "".join(self._paths)
