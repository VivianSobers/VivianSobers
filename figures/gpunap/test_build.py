import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

HERE = Path(__file__).resolve().parent
NS = {"s": "http://www.w3.org/2000/svg"}


def drawing(mode="light", data=None, freeze_at=None):
    from figures.gpunap import build
    data = data or json.loads((HERE / "data.json").read_text())
    return ET.fromstring(build.render(data, mode, freeze_at)), data


def test_every_completed_cycle_has_one_cell_grouped_by_run():
    svg, data = drawing()
    workloads = svg.findall(".//s:g[@class='workload']", NS)
    assert len(workloads) == 9
    expected = {(row["gpu"], row["tag"]): row for row in data["rows"]}
    seen = set()
    for workload in workloads:
        for run in workload.findall("s:g[@class='run']", NS):
            key = run.get("data-gpu"), run.get("data-tag")
            assert key not in seen
            seen.add(key)
            assert workload.get("data-workload") == expected[key]["workload_type"]
            assert len(run.findall("s:rect[@class='cycle']", NS)) == expected[key]["completed_cycles"]
    assert seen == set(expected)
    assert len(svg.findall(".//s:rect[@class='cycle']", NS)) == 388


def test_cells_are_square_in_bounds_and_never_overlap():
    svg, _ = drawing()
    boxes = []
    for cell in svg.findall(".//s:rect[@class='cycle']", NS):
        x, y, w, h = (float(cell.get(key)) for key in ("x", "y", "width", "height"))
        assert 10 <= w == h <= 12
        assert 320 <= x and x + w <= 1060
        assert 94 <= y and y + h <= 314
        boxes.append((x, y, x + w, y + h))
    for index, a in enumerate(boxes):
        for b in boxes[index + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_adjacent_cycles_have_two_pixel_gaps_and_runs_have_six():
    svg, _ = drawing()
    for workload in svg.findall(".//s:g[@class='workload']", NS):
        lines = {}
        for run in workload.findall("s:g[@class='run']", NS):
            cells = run.findall("s:rect", NS)
            ys = {float(cell.get("y")) for cell in cells}
            assert len(ys) == 1, "a run must stay together"
            for a, b in zip(cells, cells[1:]):
                assert float(b.get("x")) - float(a.get("x")) - float(a.get("width")) == 2
            y = ys.pop()
            left = float(cells[0].get("x"))
            right = float(cells[-1].get("x")) + float(cells[-1].get("width"))
            lines.setdefault(y, []).append((left, right))
        assert len(lines) <= 2
        for runs in lines.values():
            for a, b in zip(runs, runs[1:]):
                assert b[0] - a[1] == 6


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_static_final_state_and_accessible_description(mode):
    svg, _ = drawing(mode)
    assert svg.get("viewBox") == "0 0 1280 360"
    assert svg.find("s:title", NS).text == "388 pauses into host RAM, 388 bit-exact resumes"
    desc = svg.find("s:desc", NS).text
    assert "33 runs of 9 workload types" in desc
    assert "106 cycles, 8 runs" in desc
    assert "5 runs on gpu1" in desc
    assert "4 single-GPU NCCL, 1 managed memory" in desc
    blue = {"light": "#256abf", "dark": "#3987e5"}[mode]
    assert all(cell.get("fill") == blue for cell in svg.findall(".//s:rect[@class='cycle']", NS))
    assert "@keyframes" not in svg.find("s:style", NS).text
    assert svg.find("s:text", NS) is None


def test_counts_and_excluded_footnote_follow_the_snapshot():
    data = copy.deepcopy(json.loads((HERE / "data.json").read_text()))
    data["rows"][0]["completed_cycles"] += 1
    data["excluded"] = data["excluded"][:2]
    svg, _ = drawing(data=data)
    assert svg.find("s:title", NS).text == "389 pauses into host RAM, 389 bit-exact resumes"
    desc = svg.find("s:desc", NS).text
    assert "87 cycles, 6 runs" in desc
    assert "2 runs on gpu1" in desc
    assert "2 single-GPU NCCL" in desc
    assert "managed memory" not in desc
    assert len(svg.findall(".//s:rect[@class='cycle']", NS)) == 389


def test_freeze_preview_keeps_all_final_cells():
    svg, _ = drawing(freeze_at=2)
    assert "animation-play-state:paused!important" in svg.find("s:style", NS).text
    assert len(svg.findall(".//s:rect[@class='cycle']", NS)) == 388
