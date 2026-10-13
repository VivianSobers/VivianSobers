import copy
import re
import xml.etree.ElementTree as ET

import pytest

from figures.raster.test_build import NS, builder, data


def keyframes(css, name):
    return re.search(r'@keyframes ' + name + r'\{(.*?)\}\}', css).group(1) + '}'


def test_reveal_times_follow_common_ease_in_out_and_end_at_eight_seconds():
    build = builder()
    assert hasattr(build, "reveal_time")
    assert [build.reveal_time(f) for f in (0, 0.15625, 0.5, 0.84375, 1)] == pytest.approx(
        [0, 2.195, 4, 5.805, 8], abs=0.001)
    times = [build.reveal_time(i / 150) for i in range(1, 151)]
    assert all(a < b for a, b in zip(times, times[1:]))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_all_triangles_reveal_in_order_then_hold_and_fade(mode):
    root = ET.fromstring(builder().render(data(), mode, freeze_at=4))
    css = root.find("s:style", NS).text
    polygons = root.findall('.//s:polygon[@class="triangle"]', NS)
    assert "@keyframes triangle0" in css
    thresholds = []
    for i, polygon in enumerate(polygons):
        assert f"animation-name:triangle{i}" in polygon.attrib["style"]
        assert "animation-delay:-4.000s" in polygon.attrib["style"]
        frames = keyframes(css, f"triangle{i}")
        assert "0%{opacity:0;animation-timing-function:steps(1,end)}" in frames
        thresholds.append(float(re.search(r'([\d.]+)%\{opacity:1\}', frames).group(1)))
        assert "93.333333%{opacity:1;animation-timing-function:ease-in-out}" in frames
        assert "100%{opacity:0}" in frames
    assert all(a < b for a, b in zip(thresholds, thresholds[1:]))
    assert thresholds[-1] == pytest.approx(100 * 8 / 15, abs=0.000001)
    assert ".triangle{opacity:1;animation-duration:15s;animation-iteration-count:infinite}" in css


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_curve_and_best_marker_share_scene_clock_with_final_base_styles(mode):
    snapshot = copy.deepcopy(data())
    snapshot.update(steps=41, best_iter=20)
    root = ET.fromstring(builder().render(snapshot, mode, freeze_at=7))
    css = root.find("s:style", NS).text
    curve = root.find('.//s:polyline[@class="loss"]', NS)
    assert curve.attrib.get("clip-path") == "url(#loss-box)"
    wipe = root.find('.//s:clipPath[@id="loss-box"]/s:rect', NS)
    assert wipe.attrib["class"] == "loss-reveal"
    assert "animation-delay:-7.000s" in wipe.attrib["style"]
    frames = keyframes(css, "draw-loss")
    assert "0%{transform:scaleX(0);animation-timing-function:ease-in-out}" in frames
    assert "53.333333%,100%{transform:scaleX(1)}" in frames
    assert ".loss-reveal{transform:scaleX(1);transform-origin:848px 0;animation:draw-loss 15s linear infinite}" in css
    dot = root.find('.//s:circle[@class="best"]', NS)
    assert "animation-delay:-7.000s" in dot.attrib["style"]
    assert "26.666667%{opacity:1}" in keyframes(css, "show-best")
    assert ".best{opacity:1;animation:show-best 15s linear infinite}" in css
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in css
    assert "animation-play-state:paused!important" in css
    assert len(builder().render(snapshot, mode).encode()) < 400_000
