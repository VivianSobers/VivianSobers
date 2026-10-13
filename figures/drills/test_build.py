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
                                               (330.799, "5m31s"), (30.347, "0m30s")])
def test_duration_rounds_to_the_second(seconds, expected):
    assert build.duration(seconds) == expected


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_final_lanes_follow_recorded_times(mode):
    svg = build.render(DATA, mode)
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 1280 420"
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
            assert float(dot.attrib["r"]) >= 4
            assert dot.attrib["fill"] == color
        desc = root.find("s:desc", NS).text
        assert row["alert"] in desc
        assert f"fired {build.duration(row['fired_after_s'])}" in desc
        assert f"cleared +{build.duration(row['resolved_after_s'])}" in desc
    assert len(root.findall(".//s:g[@class='control-label']", NS)) == 1
    assert not root.findall(".//s:text", NS)
    assert "@keyframes" not in svg
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
    assert "cleared +0m47s" in labels
    assert any("2027-02-03" in label for label in labels)
    for row in data["rows"]:
        assert row["drill"] in labels
        assert row["alert"] in labels
    assert [str(tick) for tick in range(0, 36, 5)] == [label for label in labels if label.isdigit()]
