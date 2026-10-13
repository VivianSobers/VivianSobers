import re
import xml.etree.ElementTree as ET

import pytest

from figkit.color import CATEGORICAL, INK, MUTED
from figures.qk.test_build import NS, builder, data


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_medians_and_labels_use_each_forms_palette_colour(mode):
    root = ET.fromstring(builder().render(data(), mode))
    markers = root.findall('.//s:line[@class="median"]', NS)
    for marker, form, hue in zip(markers, ("exact", "no_rope", "plain"), ("blue", "aqua", "orange")):
        colour = CATEGORICAL[hue][mode]
        assert marker.attrib["stroke"] == colour
        label = root.find(f'.//s:g[@class="label {form}"]', NS)
        assert label.attrib["fill"] == colour
        assert label.findall("s:use", NS)
    parents = {child: parent for parent in root.iter() for child in parent}
    for glyph in root.findall(".//s:use", NS):
        node = parents[glyph]
        while "fill" not in node.attrib:
            node = parents[node]
        if not node.attrib.get("class", "").startswith("label "):
            assert node.attrib["fill"] in (INK[mode], MUTED[mode])


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_moving_heads_hold_stop_colours_and_reset_to_plain_while_hidden(mode):
    root = ET.fromstring(builder().render(data(), mode, freeze_at=4))
    css = root.find("s:style", NS).text
    paint = re.search(r"@keyframes paint(.*?)\.head", css)[1]
    orange, aqua, blue = (CATEGORICAL[hue][mode] for hue in ("orange", "aqua", "blue"))
    assert paint == (
        f"{{0%,12.5%{{fill:{orange};opacity:0.85}}"
        f"21.875%,34.375%{{fill:{aqua};opacity:0.85}}"
        f"43.75%,87.5%{{fill:{blue};opacity:0.85}}93.75%{{fill:{blue};opacity:0}}"
        f"93.751%{{fill:{orange};opacity:0}}100%{{fill:{orange};opacity:0.85}}}}"
    )
    desc = root.find("s:desc", NS).text
    assert "orange at the plain product, aqua with rotary left out, and blue at the exact form" in desc
