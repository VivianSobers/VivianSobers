import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import build
from figkit.color import INK, MUTED

NS = {"svg": "http://www.w3.org/2000/svg"}
DATA = json.loads((Path(build.__file__).parent / "attention.json").read_text())
NAMES = ["First-token head", "Previous-token head", "Induction head", "Broad head"]


def names(root):
    row = root.find(".//svg:g[@class='head-names']", NS)
    assert row is not None, "missing head names under the caption"
    return list(row)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_head_names_form_one_small_row_below_caption_without_changing_height(mode):
    root = ET.fromstring(build.render(DATA, mode))
    assert root.attrib["height"] == "461"
    groups = names(root)
    assert [group.attrib["aria-label"] for group in groups] == NAMES
    last = 40.0
    face = build.faces()["body"]
    for group, name in zip(groups, NAMES):
        uses = group.findall("svg:use", NS)
        glyphs, _ = face.shape(name, 13)
        expected = [face.outline(glyph.name) for glyph in glyphs if face.outline(glyph.name)]
        actual = [root.find(f"svg:defs/svg:path[@id='{use.attrib['href'][1:]}']", NS).attrib["d"]
                  for use in uses]
        assert actual == expected
        positions = [re.match(r"translate\(([-\d.]+) ([-\d.]+)\) scale\(([-\d.]+)", use.attrib["transform"])
                     for use in uses]
        assert all(float(pos[2]) == 124 for pos in positions)
        assert all(float(pos[3]) == pytest.approx(13 / face.units_per_em, abs=0.000005) for pos in positions)
        left = float(positions[0][1])
        assert left >= last
        last = left + face.advance(name, 13)
    assert last < 488


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_head_highlights_share_scene_timing_and_induction_static_state(mode):
    root = ET.fromstring(build.render(DATA, mode, freeze_at=7.5))
    groups = names(root)
    css = root.find("svg:style", NS).text
    assert ".s2{opacity:1}" in css
    assert ".c,.l{opacity:0;animation:on 22s ease-in-out infinite backwards}" in css
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in css
    for s, (group, expected_delay) in enumerate(zip(groups, [-7.5, -2, 3.5, 9])):
        assert group.attrib["fill"] == MUTED[mode]
        active = group.find("svg:g", NS)
        assert active.attrib["class"] == f"l s{s}"
        assert active.attrib["fill"] == INK[mode]
        assert active.attrib["style"] == f"animation-delay:{expected_delay:.3f}s"
        assert [use.attrib for use in active] == [use.attrib for use in group.findall("svg:use", NS)]
        scene = root.find(f".//svg:g[@class='l s{s}'][svg:g]", NS)
        assert scene.attrib["style"] == active.attrib["style"]
