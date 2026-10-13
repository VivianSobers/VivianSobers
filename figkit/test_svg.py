import xml.etree.ElementTree as ET

import pytest

from figkit.svg import delay, document


def test_document_escapes_title_and_desc_as_xml_text():
    title = 'Heads <cells> & "weights"'
    desc = "A > B & C < D"
    svg = document(1280, 380, title, desc, "", "", "")
    root = ET.fromstring(svg)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert root.find("svg:title", ns).text == title
    assert root.find("svg:desc", ns).text == desc
    assert "&lt;cells&gt; &amp;" in svg


def test_document_preserves_the_wrapper_and_raw_svg_fragments():
    svg = document(1280.0, 380, "Heads", "Weights", ".cell{opacity:1}", '<path id="cell"/>', '<use href="#cell"/>')
    assert svg.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 380" '
        'width="1280" height="380" role="img" aria-labelledby="title desc">'
        '<title id="title">Heads</title><desc id="desc">Weights</desc><style>.cell{opacity:1}'
    )
    assert svg.endswith('</style><defs><path id="cell"/></defs><use href="#cell"/></svg>\n')


@pytest.mark.parametrize("freeze_at", [None, 0.0, 6.5])
def test_document_always_appends_reduced_motion_rule(freeze_at):
    svg = document(1280, 380, "", "", ".cell{animation:on 12s infinite}", "", "", freeze_at)
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>" in svg


@pytest.mark.parametrize("freeze_at", [None, 0.0, 6.5])
def test_document_pauses_all_animations_only_when_frozen(freeze_at):
    svg = document(1280, 380, "", "", "", "", "", freeze_at)
    assert ("*{animation-play-state:paused!important}" in svg) == (freeze_at is not None)


@pytest.mark.parametrize(
    "seconds,freeze_at,expected",
    [(1.25, None, "animation-delay:1.250s"), (1.25, 0.0, "animation-delay:1.250s"),
     (1.25, 6.5, "animation-delay:-5.250s")],
)
def test_delay_offsets_animation_time_for_frozen_frames(seconds, freeze_at, expected):
    assert delay(seconds, freeze_at) == expected
