import json
import math
import xml.etree.ElementTree as ET
from functools import cache

import pytest

import build
from figkit.color import CATEGORICAL, INK, MUTED, RAMP, from_oklab, hue_ramp, to_oklab

NS = {"s": "http://www.w3.org/2000/svg"}
HUES = {"first_token": "blue", "previous_token": "aqua", "induction": "magenta", "spread": "violet"}
DATA = json.loads((build.HERE / "attention.json").read_text())


@cache
def rendered(mode):
    return ET.fromstring(build.render(DATA, mode, freeze_at=13))


def stops(role, mode):
    ramp = RAMP if role == "first_token" else hue_ramp(CATEGORICAL[HUES[role]][mode])
    return ramp if mode == "light" else ramp[::-1]


def expected_color(weight, ramp):
    position = math.sqrt(weight) * (len(ramp) - 1)
    k = min(int(position), len(ramp) - 2)
    fraction = position - k
    if fraction in (0, 1):
        return ramp[k + int(fraction)]
    return from_oklab(*(a + (b - a) * fraction for a, b in zip(to_oklab(ramp[k]), to_oklab(ramp[k + 1]))))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_each_scene_colors_its_measured_cells_with_its_own_ramp(mode):
    root = rendered(mode)
    for s, head in enumerate(DATA["heads"]):
        paths = root.findall(f'.//s:g[@class="c s{s}"]/s:path', NS)
        weights = [w for i, row in enumerate(head["pattern"]) for w in row[:i + 1] if w >= build.THRESHOLD]
        assert [path.attrib["fill"] for path in paths] == [expected_color(w, stops(head["role"], mode)) for w in weights]
    lattice = root.find("s:path", NS)
    assert lattice.attrib["fill"] == (RAMP[0] if mode == "light" else RAMP[-1])
    assert float(lattice.attrib["opacity"]) == build.LATTICE_OPACITY[mode]


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_active_name_has_a_hue_diamond_and_neutral_text(mode):
    root = rendered(mode)
    names = root.find('s:g[@class="head-names"]', NS)
    for s, head in enumerate(DATA["heads"]):
        name = names.find(f's:g[@aria-label="{build.ROLE_TEXT[head["role"]][0]}"]', NS)
        assert name.attrib["fill"] == MUTED[mode]
        active = name.find(f's:g[@class="l s{s}"]', NS)
        assert active.attrib["fill"] == INK[mode]
        diamond = active.find("s:path", NS)
        assert diamond is not None
        assert diamond.attrib["fill"] == CATEGORICAL[HUES[head["role"]]][mode]
        assert len(diamond.attrib["d"].split("L")) == 4
        assert active.findall("s:use", NS)
        assert active.attrib["style"] == build.delay(s * build.Timing().scene, 13)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_each_legend_fades_with_its_scene_and_matches_its_cells(mode):
    root = rendered(mode)
    legends = root.findall('.//s:g[@class="legend"]', NS)
    assert len(legends) == len(DATA["heads"])
    for s, (legend, head) in enumerate(zip(legends, DATA["heads"])):
        active = legend.find(f's:g[@class="l s{s}"]', NS)
        assert active is not None
        assert active.attrib["style"] == build.delay(s * build.Timing().scene, 13)
        assert [p.attrib["fill"] for p in active.findall("s:path", NS)] == list(stops(head["role"], mode))
    css = root.find("s:style", NS).text
    assert ".s2{opacity:1}" in css
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in css
    assert len(build.render(DATA, mode).encode()) < 400_000
