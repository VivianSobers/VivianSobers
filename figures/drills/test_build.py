import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from figures.drills import build
from figkit.color import BLUE, EMBER, FAINT

DATA = json.loads((Path(__file__).parent / "data.json").read_text())
NS = {"s": "http://www.w3.org/2000/svg"}


def test_time_axis_endpoints_and_spacing():
    geometry = build.Geometry()
    assert build.time_x(0, geometry) == geometry.left
    assert build.time_x(36, geometry) == geometry.right
    step = (geometry.right - geometry.left) * 5 / 36
    for minute in range(0, 31, 5):
        assert build.time_x(minute + 5, geometry) - build.time_x(minute, geometry) == pytest.approx(step)


@pytest.mark.parametrize("seconds, expected", [(105.081, "1m45s"), (960.568, "16m01s"),
                                               (330.799, "5m31s"), (30.347, "30s"), (30.987, "31s"),
                                               (0, "0s"), (59.6, "1m00s"), (60, "1m00s")])
def test_duration_rounds_to_the_second(seconds, expected):
    assert build.duration(seconds) == expected


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_final_lanes_follow_recorded_times(mode):
    svg = build.render(DATA, mode)
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 1280 560"
    lanes = root.findall(".//s:g[@class='lane']", NS)
    assert len(lanes) == len(DATA["rows"])
    for lane, row in zip(lanes, DATA["rows"]):
        assert lane.attrib["data-drill"] == row["drill"]
        start = build.time_x(row["fired_after_s"] / 60)
        end = build.time_x((row["fired_after_s"] + row["resolved_after_s"]) / 60)
        baseline = lane.find("s:line[@class='baseline']", NS)
        segment = lane.find("s:line[@class='firing']", NS)
        control = lane.find("s:line[@class='control']", NS)
        assert baseline.attrib["stroke"] == FAINT[mode]
        assert float(segment.attrib["x1"]) == pytest.approx(start, abs=0.01)
        assert float(segment.attrib["x2"]) == pytest.approx(end, abs=0.01)
        assert segment.attrib["stroke"] == EMBER[mode]
        assert float(control.attrib["x1"]) == pytest.approx(start, abs=0.01)
        assert float(control.attrib["x2"]) == build.Geometry().right
        assert control.attrib["stroke"] == EMBER[mode]
        assert "stroke-dasharray" in control.attrib
        for kind, x, color in (("fired", start, EMBER[mode]), ("cleared", end, BLUE[mode])):
            dot = lane.find(f"s:circle[@class='{kind}']", NS)
            assert float(dot.attrib["cx"]) == pytest.approx(x, abs=0.01)
            assert float(dot.attrib["r"]) >= 5
            assert dot.attrib["fill"] == color
        desc = root.find("s:desc", NS).text
        assert row["alert"] in desc
        assert f"fired {build.duration(row['fired_after_s'])}" in desc
        assert f"cleared +{build.duration(row['resolved_after_s'])}" in desc
    assert len(root.findall(".//s:g[@class='control-label']", NS)) == 1
    assert not root.findall(".//s:text", NS)
    assert "@keyframes sweep" in svg
    assert ".fired,.cleared,.fired-label,.cleared-label,.control-label{opacity:1}" in svg
    assert "prefers-reduced-motion:reduce" in svg
    assert len(svg.encode()) < 400_000


def test_labels_use_supplied_data(monkeypatch):
    data = copy.deepcopy(DATA)
    data["config"]["run_started"] = "2027-02-03T12:00:00Z"
    data["rows"][0]["fired_after_s"] = 123
    data["rows"][0]["resolved_after_s"] = 47
    labels = []
    original = build.Outliner.run

    def capture(self, face, text, *args, **kwargs):
        labels.append(text)
        return original(self, face, text, *args, **kwargs)

    monkeypatch.setattr(build.Outliner, "run", capture)
    build.render(data, "light", freeze_at=7.5)
    assert "fired 2m03s" in labels
    assert "cleared +47s" in labels
    assert any("2027-02-03" in label for label in labels)
    for row in data["rows"]:
        assert row["drill"] in labels
        assert row["alert"] in labels
    assert [str(tick) for tick in range(0, 35, 5)] == [label for label in labels if label.isdigit()]
    assert labels.count("35 min") == 1
    assert labels.count("fault") == 1


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_each_lane_shows_the_fault_and_wait_until_firing(mode):
    data = copy.deepcopy(DATA)
    data["rows"][0]["fired_after_s"] = 240
    root = ET.fromstring(build.render(data, mode))
    lanes = root.findall(".//s:g[@class='lane']", NS)
    for lane, row in zip(lanes, data["rows"]):
        baseline = lane.find("s:line[@class='baseline']", NS)
        y = float(baseline.attrib["y1"])
        fault = lane.find("s:line[@class='fault']", NS)
        wait = lane.find("s:line[@class='wait']", NS)
        assert fault is not None
        assert wait is not None
        assert float(fault.attrib["x1"]) == float(fault.attrib["x2"]) == build.time_x(0)
        assert float(fault.attrib["y1"]) == y - 6
        assert float(fault.attrib["y2"]) == y + 6
        assert fault.attrib["stroke"] == wait.attrib["stroke"] == EMBER[mode]
        assert float(fault.attrib["stroke-width"]) == float(wait.attrib["stroke-width"]) == 2.5
        assert float(wait.attrib["x1"]) == build.time_x(0)
        assert float(wait.attrib["x2"]) == pytest.approx(build.time_x(row["fired_after_s"] / 60), abs=0.01)
        assert float(wait.attrib["y1"]) == float(wait.attrib["y2"]) == y
        assert float(wait.attrib["opacity"]) == 0.35
    assert len(root.findall(".//s:g[@class='fault-label']", NS)) == 1
    assert lanes[0].find("s:g[@class='fault-label']", NS) is not None
    assert "wait" in root.find("s:desc", NS).text


def test_clock_sweeps_then_holds_and_fades_with_a_final_base_state():
    root = ET.fromstring(build.render(DATA, "light"))
    css = root.find("s:style", NS).text
    playhead = root.find(".//s:line[@class='playhead']", NS)
    assert playhead is not None
    assert float(playhead.attrib["x1"]) == float(playhead.attrib["x2"]) == 390
    assert "transform:translateX(850px)" in css
    assert "70.588235%" in css
    assert "94.117647%" in css
    assert "17s linear infinite" in css
    assert "17s ease-in-out infinite" in css
    clip = root.find(".//s:clipPath[@id='clock-window']/s:rect", NS)
    assert clip is not None
    assert float(clip.attrib["width"]) == 850
    assert ".fired,.cleared,.fired-label,.cleared-label,.control-label{opacity:1}" in css
    assert ".playhead{transform:translateX(850px)}" in css
    for lane in root.findall(".//s:g[@class='lane']", NS):
        for kind in ("wait", "firing", "control"):
            assert lane.find(f"s:line[@class='{kind}']", NS).attrib["clip-path"] == "url(#clock-window)"


def test_event_reveals_follow_the_supplied_times_and_freeze_together():
    import re

    data = copy.deepcopy(DATA)
    data["rows"][0]["fired_after_s"] = 540
    data["rows"][0]["resolved_after_s"] = 180
    root = ET.fromstring(build.render(data, "dark", freeze_at=6))
    css = root.find("s:style", NS).text
    lanes = root.findall(".//s:g[@class='lane']", NS)
    for index, (lane, row) in enumerate(zip(lanes, data["rows"])):
        for kind, seconds in (("fired", row["fired_after_s"]),
                              ("cleared", row["fired_after_s"] + row["resolved_after_s"])):
            name = f"{kind}-{index}"
            match = re.search(rf"@keyframes {name}\{{0%\{{opacity:0\}}([\d.]+)%\{{opacity:1\}}100%\{{opacity:1\}}\}}", css)
            assert match is not None
            assert float(match[1]) == pytest.approx(seconds / 2160 * 12 / 17 * 100, abs=0.000001)
            dot = lane.find(f"s:circle[@class='{kind}']", NS)
            label = lane.find(f"s:g[@class='{kind}-label']", NS)
            for mark in (dot, label):
                assert mark is not None
                assert f"animation:{name} 17s steps(1,end) infinite" in mark.attrib["style"]
                assert "animation-delay:-6.000s" in mark.attrib["style"]
    assert "animation-delay:-6.000s" in root.find(".//s:line[@class='playhead']", NS).attrib["style"]
    assert "animation-play-state:paused!important" in css
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in css


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_text_is_readable_and_has_room_at_readme_width(monkeypatch, mode):
    runs = []
    original = build.Outliner.run

    def capture(self, face, text, x, y, size, anchor="start"):
        width = face.advance(text, size)
        left = x - {"start": 0, "middle": width / 2, "end": width}[anchor]
        runs.append((text, size, (left, y - size, left + width, y + size / 4)))
        return original(self, face, text, x, y, size, anchor)

    monkeypatch.setattr(build.Outliner, "run", capture)
    build.render(DATA, mode, freeze_at=13)
    assert runs[0][1] == 26
    assert runs[1][1] == 18
    assert all(size >= 16 for _, size, _ in runs)
    for text, _, (left, top, right, bottom) in runs:
        assert 40 <= left < right <= 1240, text
        assert 0 <= top < bottom <= build.Geometry().height - 14, text
    for index, (text, _, box) in enumerate(runs):
        for other, _, next_box in runs[index + 1:]:
            assert (box[2] + 4 <= next_box[0] or next_box[2] + 4 <= box[0]
                    or box[3] + 4 <= next_box[1] or next_box[3] + 4 <= box[1]), (text, other)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_marks_scale_with_the_larger_labels(mode):
    root = ET.fromstring(build.render(DATA, mode))
    for line in root.findall(".//s:line", NS):
        assert float(line.attrib["stroke-width"]) == 2.5
    for dot in root.findall(".//s:circle", NS):
        assert float(dot.attrib["r"]) >= 5
    lanes = root.findall(".//s:g[@class='lane']", NS)
    for lane in lanes:
        labels = lane.find("s:g", NS)
        xs = [float(use.attrib["transform"].split("(")[1].split()[0])
              for use in labels.findall("s:use", NS)]
        assert max(xs) + 16 < build.Geometry().left - 20
