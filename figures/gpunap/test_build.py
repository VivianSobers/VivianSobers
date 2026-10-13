import copy
import json
import re
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
        assert 94 <= y and y + h <= float(svg.get("height")) - 49
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
    assert svg.get("viewBox") == "0 0 1280 385"
    assert svg.find("s:title", NS).text == "388 pauses into host RAM, 388 bit-exact resumes"
    desc = svg.find("s:desc", NS).text
    assert "33 runs of 9 workload types" in desc
    assert "106 cycles, 8 runs" in desc
    assert "5 runs on gpu1" in desc
    assert "4 single-GPU NCCL, 1 managed memory" in desc
    blue = {"light": "#256abf", "dark": "#3987e5"}[mode]
    assert all(cell.get("fill") == blue for cell in svg.findall(".//s:rect[@class='cycle']", NS))
    assert "@keyframes" in svg.find("s:style", NS).text
    counters = svg.findall(".//s:g[@class='counter']", NS)
    assert [int(group.get("data-count")) for group in counters if group.get("opacity") == "1"] == [388]
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in svg.find("s:style", NS).text
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


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_workload_cell_boxes_have_at_least_twelve_pixels_between_rows(mode):
    svg, _ = drawing(mode)
    previous_bottom = None
    for workload in svg.findall(".//s:g[@class='workload']", NS):
        cells = workload.findall(".//s:rect[@class='cycle']", NS)
        top = min(float(cell.get("y")) for cell in cells)
        bottom = max(float(cell.get("y")) + float(cell.get("height")) for cell in cells)
        if previous_bottom is not None:
            assert top - previous_bottom >= 12, workload.get("data-workload")
        previous_bottom = bottom


def test_labels_follow_the_first_cell_line():
    svg, _ = drawing()
    for workload in svg.findall(".//s:g[@class='workload']", NS):
        cells = workload.findall(".//s:rect[@class='cycle']", NS)
        baseline = min(float(cell.get("y")) for cell in cells) + 10
        labels = workload.find("s:g", NS).findall("s:use", NS)
        assert labels
        assert all(float(label.get("transform").split(")")[0].split()[-1]) == baseline for label in labels)


def test_canvas_and_following_rows_grow_when_another_workload_wraps():
    data = copy.deepcopy(json.loads((HERE / "data.json").read_text()))
    for run in data["rows"]:
        if run["workload_type"] == "CNN with cuDNN":
            run["completed_cycles"] = 30
    svg, _ = drawing(data=data)
    workloads = svg.findall(".//s:g[@class='workload']", NS)
    first_lines = [min(float(cell.get("y")) for cell in row.findall(".//s:rect", NS)) for row in workloads]
    assert first_lines == [94, 132, 170, 208, 234, 260, 286, 312, 338]
    assert svg.get("viewBox") == "0 0 1280 397"
    note = svg.findall("s:g", NS)[1].findall("s:use", NS)[-1]
    assert float(note.get("transform").split(")")[0].split()[-1]) == 377


def frames(css, name):
    body = re.search(r"@keyframes " + name + r"\{((?:[^{}]*\{[^{}]*\})+)\}", css).group(1)
    return [(float(at), dict(item.split(":") for item in props.split(";") if item))
            for at, props in re.findall(r"([\d.]+)%\{([^{}]*)\}", body)]


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_cells_pause_for_point_four_seconds_in_a_left_to_right_sweep(mode):
    svg, _ = drawing(mode)
    css = svg.find("s:style", NS).text
    cells = svg.findall(".//s:rect[@class='cycle']", NS)
    ember = {"light": "#d9622b", "dark": "#e0702f"}[mode]
    events = []
    for cell in cells:
        name = re.search(r"animation:(\w+) ([\d.]+)s steps\(1,end\) infinite", cell.get("style", ""))
        assert name, "each cell needs a discrete pause/resume animation"
        loop = float(name[2])
        assert 12 <= loop <= 20
        keys = frames(css, name[1])
        paused = next(at for at, props in keys if props.get("fill") == ember)
        resumed = next(at for at, props in keys if at > paused and props.get("fill") == cell.get("fill"))
        assert (resumed - paused) * loop / 100 == pytest.approx(0.4, abs=0.00002)
        assert keys[0][1]["opacity"] == "0.18"
        assert keys[-1][1] == {"fill": cell.get("fill"), "opacity": "1"}
        events.append((paused, float(cell.get("x")), resumed))
    events.sort()
    assert [x for _, x, _ in events] == sorted(x for _, x, _ in events)
    assert events[-1][2] * loop / 100 < loop - 3


def test_counter_steps_match_every_resumed_cell_and_only_one_value_is_visible():
    svg, data = drawing()
    css = svg.find("s:style", NS).text
    counters = svg.findall(".//s:g[@class='counter']", NS)
    total = sum(row["completed_cycles"] for row in data["rows"])
    assert [int(group.get("data-count")) for group in counters] == list(range(total + 1))
    resumes = []
    for cell in svg.findall(".//s:rect[@class='cycle']", NS):
        name = re.search(r"animation:(\w+)", cell.get("style"))[1]
        resumes.append(frames(css, name)[-2][0])
    resumes.sort()
    intervals = []
    for value, group in enumerate(counters):
        assert group.findall("s:use", NS), "counter numbers must be outlined"
        name = re.search(r"animation:(\w+) [\d.]+s steps\(1,end\) infinite", group.get("style"))[1]
        keys = frames(css, name)
        start = next(at for at, props in keys if props["opacity"] == "1")
        end = next((at for at, props in keys if at > start and props["opacity"] == "0"), 100)
        assert start == (0 if value == 0 else resumes[value - 1])
        assert end == (100 if value == total else resumes[value])
        intervals.append((start, end))
    assert all(a[1] == b[0] for a, b in zip(intervals, intervals[1:]))
    assert svg.find(".//s:script", NS) is None


def test_animated_counter_tracks_changed_data_and_stays_below_size_limit():
    data = copy.deepcopy(json.loads((HERE / "data.json").read_text()))
    data["rows"][0]["completed_cycles"] += 1
    svg, _ = drawing(data=data)
    counters = svg.findall(".//s:g[@class='counter']", NS)
    assert len(counters) == 390
    assert counters[-1].get("data-count") == "389"
    from figures.gpunap import build
    for mode in ("light", "dark"):
        assert len(build.render(data, mode).encode()) < 400_000


def test_every_animation_freezes_on_the_same_clock_and_loop_fades_seamlessly():
    svg, _ = drawing(freeze_at=7.5)
    css = svg.find("s:style", NS).text
    animated = [element for element in svg.iter() if "animation:" in element.get("style", "")]
    assert len(animated) >= 777
    assert all("animation-delay:-7.500s" in element.get("style") for element in animated)
    scene = frames(css, "sweep")
    assert scene[0][1] == scene[-1][1] == {"opacity": "0"}
    assert any(props == {"opacity": "1"} for _, props in scene)
