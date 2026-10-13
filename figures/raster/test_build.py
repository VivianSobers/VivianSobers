import base64
import copy
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
NS = {"s": "http://www.w3.org/2000/svg"}


def builder():
    from figures.raster import build
    return build


def data():
    return json.loads((HERE / "data.json").read_text())


def test_normalized_mapping_preserves_corners_and_outside_vertices():
    build = builder()
    box = build.Box(410, 126, 300, 300)
    for vertex, expected in (((0, 0), (410, 126)), ((1, 1), (710, 426)),
                             ((0.5, 0.25), (560, 201)), ((-0.1, 1.2), (380, 486))):
        assert build.panel_point(vertex, box) == pytest.approx(expected)


def test_loss_mapping_is_linear_in_steps_and_logarithmic_in_loss():
    build = builder()
    snapshot = data()
    box = build.Box(848, 156, 392, 226)
    assert build.loss_point(0, snapshot["first_loss"], snapshot, box) == pytest.approx((848, 156))
    assert build.loss_point(snapshot["steps"] - 1, 1e-5, snapshot, box) == pytest.approx((1240, 382))
    middle = math.sqrt(snapshot["first_loss"] * 1e-5)
    assert build.loss_point((snapshot["steps"] - 1) / 2, middle, snapshot, box) == pytest.approx((1044, 269))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_scene_embeds_only_target_and_preserves_triangle_paint_order(mode):
    build = builder()
    snapshot = data()
    root = ET.fromstring(build.render(snapshot, mode))
    assert root.attrib["viewBox"] == "0 0 1280 500"
    images = root.findall(".//s:image", NS)
    assert len(images) == 1
    prefix, encoded = images[0].attrib["href"].split(",", 1)
    assert prefix == "data:image/png;base64"
    assert base64.b64decode(encoded) == (HERE / "target.png").read_bytes()
    assert len(base64.b64decode(encoded)) <= 60_000
    scene = root.find('.//s:g[@class="scene"]', NS)
    assert scene.attrib["clip-path"] == "url(#scene-box)"
    clip = root.find('.//s:clipPath[@id="scene-box"]/s:rect', NS)
    background = scene.find("s:rect", NS)
    for key in ("width", "height"):
        assert images[0].attrib[key] == background.attrib[key] == clip.attrib[key]
    assert background.attrib["fill"] == build.rgb(snapshot["background"])
    box = build.Box(*(float(background.attrib[key]) for key in ("x", "y", "width", "height")))
    polygons = scene.findall("s:polygon", NS)
    assert len(polygons) == len(snapshot["triangles"])
    for polygon, triangle in zip(polygons, snapshot["triangles"]):
        actual = [tuple(map(float, point.split(","))) for point in polygon.attrib["points"].split()]
        for point, vertex in zip(actual, triangle["verts"]):
            assert point == pytest.approx(build.panel_point(vertex, box), abs=0.001)
        assert polygon.attrib["fill"] == build.rgb(triangle["color"])
        assert float(polygon.attrib["fill-opacity"]) == triangle["alpha"]


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_loss_curve_includes_best_step_and_all_recorded_points(mode):
    build = builder()
    from figkit.color import CATEGORICAL
    snapshot = data()
    root = ET.fromstring(build.render(snapshot, mode))
    curve = root.find('.//s:polyline[@class="loss"]', NS)
    assert curve.attrib["stroke"] == CATEGORICAL["magenta"][mode]
    assert curve.attrib["stroke-width"] == "2.5"
    assert curve.attrib["fill"] == "none"
    box = build.Box(848, 180, 392, 226)
    expected = sorted(snapshot["loss"] + [{"iter": snapshot["best_iter"], "loss": snapshot["best_loss"]}], key=lambda p: p["iter"])
    points = [tuple(map(float, point.split(","))) for point in curve.attrib["points"].split()]
    assert len(points) == len(expected)
    for actual, point in zip(points, expected):
        assert actual == pytest.approx(build.loss_point(point["iter"], point["loss"], snapshot, box), abs=0.001)
    dot = root.find('.//s:circle[@class="best"]', NS)
    assert (float(dot.attrib["cx"]), float(dot.attrib["cy"])) == pytest.approx(
        build.loss_point(snapshot["best_iter"], snapshot["best_loss"], snapshot, box), abs=0.001)
    assert dot.attrib["fill"] == CATEGORICAL["magenta"][mode]
    assert float(dot.attrib["r"]) >= 5
    desc = root.find("s:desc", NS).text
    assert f"loss fell {snapshot['first_loss'] / snapshot['best_loss']:.0f}× (best at step {snapshot['best_iter']})" in desc


def test_titles_and_best_ratio_follow_supplied_data():
    build = builder()
    snapshot = copy.deepcopy(data())
    snapshot["triangles"] = snapshot["triangles"][:2]
    snapshot.update(steps=41, first_loss=0.1, best_loss=0.002, last_loss=0.004, best_iter=23, ratio=25)
    snapshot["loss"] = [{"iter": 0, "loss": 0.1}, {"iter": 40, "loss": 0.004}]
    snapshot["config"].update(seed=7)
    root = ET.fromstring(build.render(snapshot, "light"))
    assert root.find("s:title", NS).text == "An image, rebuilt from 2 triangles by gradient descent"
    desc = root.find("s:desc", NS).text
    assert "seed 7, 41 steps on one CPU core" in desc
    assert "loss fell 50× (best at step 23)" in desc
    assert "loss fell 25×" not in desc


def test_renderer_is_self_contained_and_supports_frozen_previews():
    build = builder()
    for mode in ("light", "dark"):
        svg = build.render(data(), mode, freeze_at=2)
        root = ET.fromstring(svg)
        assert len(svg.encode()) < 400_000
        assert root.find("s:title", NS).text and root.find("s:desc", NS).text
        assert not root.findall(".//s:text", NS)
        assert not root.findall(".//s:script", NS)
        assert not root.findall(".//s:foreignObject", NS)
        assert "https://" not in svg
        assert "@keyframes draw-loss" in svg
        assert "animation-delay:-2.000s" in svg
        assert "animation-play-state:paused!important" in svg
        assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in svg


def test_scene_encodes_linear_rgb_before_writing_fills():
    snapshot = copy.deepcopy(data())
    snapshot["background"] = [0.25, 0.5, 0.75]
    snapshot["triangles"][0]["color"] = [0, 0.0031308, 1]
    root = ET.fromstring(builder().render(snapshot, "light"))
    scene = root.find('.//s:g[@class="scene"]', NS)
    assert scene.find("s:rect", NS).attrib["fill"] == "#89bce1"
    assert scene.find("s:polygon", NS).attrib["fill"] == "#000aff"


def test_loss_ticks_use_decades_and_regular_step_intervals():
    snapshot = data()
    root = ET.fromstring(builder().render(snapshot, "light"))
    ticks = root.findall('.//s:g[@class="loss-tick"]', NS)
    assert [int(tick.attrib["data-exponent"]) for tick in ticks] == [-5, -4, -3, -2]
    for tick in ticks:
        uses = tick.findall("s:use", NS)
        assert len(uses) == 4
        transforms = [use.attrib["transform"] for use in uses]
        baselines = [float(t.split(")")[0].split()[-1]) for t in transforms]
        assert baselines[2:] == pytest.approx([baselines[0] - 6.8] * 2)
        y = float(tick.attrib["data-y"])
        assert 180 <= y <= 406
    ys = [float(tick.attrib["data-y"]) for tick in ticks]
    assert [a-b for a,b in zip(ys, ys[1:])] == pytest.approx([ys[0]-ys[1]] * 3)
    steps = root.findall('.//s:g[@class="step-tick"]', NS)
    assert [int(tick.attrib["data-step"]) for tick in steps] == [0, 200, 400, 600, snapshot["steps"] - 1]
    shorter = copy.deepcopy(snapshot)
    shorter.update(steps=401)
    root = ET.fromstring(builder().render(shorter, "light"))
    assert [int(t.attrib["data-step"]) for t in root.findall('.//s:g[@class="step-tick"]', NS)] == [0, 200, 400]


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_all_label_runs_are_readable_and_inside_canvas(monkeypatch, mode):
    from figkit.text import Outliner, run_start
    runs = []
    original = Outliner.run

    def record(self, face, text, x, y, size, anchor="start"):
        runs.append((face, text, x, y, size, anchor))
        return original(self, face, text, x, y, size, anchor)

    monkeypatch.setattr(Outliner, "run", record)
    root = ET.fromstring(builder().render(data(), mode))
    assert runs[0][4] == 26
    assert runs[1][4] == 18
    assert all(run[4] >= 16 for run in runs)
    height = float(root.attrib["height"])
    for face, text, x, y, size, anchor in runs:
        width = face.advance(text, size)
        left = run_start(x, width, anchor)
        assert left >= 40
        assert left + width <= 1240
        assert y - size >= 0
        assert y + size * 0.25 <= height - 12
    image = root.find("s:image", NS)
    panel_top = float(image.attrib["y"])
    panel_bottom = panel_top + float(image.attrib["height"])
    headings = [run for run in runs if run[1] in ("Target image", "Fitted triangles")]
    assert all(run[3] + 8 <= panel_top for run in headings)
    footer = next(run for run in runs if run[1].startswith("Drawn in paint order"))
    assert footer[3] - footer[4] >= panel_bottom + 12


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_all_drawn_lines_scale_with_labels(mode):
    root = ET.fromstring(builder().render(data(), mode))
    for element in root.findall(".//s:line", NS):
        assert float(element.attrib["stroke-width"]) == 2.5
    borders = root.find('.//s:g[@fill="none"]', NS)
    assert float(borders.attrib["stroke-width"]) == 2.5


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("freeze_at", [None, 2, 13])
def test_loss_label_matches_magenta_marks_and_other_text_stays_neutral(mode, freeze_at):
    from figkit.color import CATEGORICAL, INK, MUTED
    root = ET.fromstring(builder().render(data(), mode, freeze_at=freeze_at))
    heading, labels, ratio = root.findall("s:g", NS)[:3]
    assert heading.attrib["fill"] == INK[mode]
    assert labels.attrib["fill"] == MUTED[mode]
    assert ratio.findall("s:use", NS)
    assert ratio.attrib["fill"] == CATEGORICAL["magenta"][mode]
    assert root.find('.//s:polyline[@class="loss"]', NS).attrib["stroke"] == ratio.attrib["fill"]
    assert root.find('.//s:circle[@class="best"]', NS).attrib["fill"] == ratio.attrib["fill"]
    assert "The magenta dot marks the best scene's step." in root.find("s:desc", NS).text
