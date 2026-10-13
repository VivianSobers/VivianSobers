import copy
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import median

import pytest

ROOT = Path(__file__).resolve().parents[2]
NS = {"s": "http://www.w3.org/2000/svg"}


def builder():
    from figures.qk import build
    return build


def data():
    return json.loads((Path(__file__).parent / "data.json").read_text())


def test_log_x_has_requested_edges():
    build = builder()
    geometry = build.Geometry()
    assert build.log_x(1e-8, geometry) == pytest.approx(geometry.left)
    assert build.log_x(1e3, geometry) == pytest.approx(geometry.right)


def test_log_x_spaces_decades_evenly():
    build = builder()
    positions = [build.log_x(10 ** exponent) for exponent in range(-8, 4)]
    assert all(b - a == pytest.approx(positions[1] - positions[0]) for a, b in zip(positions, positions[1:]))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_static_state_places_every_head_at_its_exact_error(mode):
    build = builder()
    from figkit.color import BLUE
    snapshot = data()
    svg = build.render(snapshot, mode)
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 1280 430"
    dots = root.findall('.//s:circle[@class="head"]', NS)
    assert len(dots) == len(snapshot["rows"])
    for dot, row in zip(dots, snapshot["rows"]):
        assert float(dot.attrib["cx"]) == pytest.approx(build.log_x(row["exact"]), abs=0.01)
        assert dot.attrib["fill"] == BLUE[mode]
    layers = {row["layer"]: float(dot.attrib["cy"]) for dot, row in zip(dots, snapshot["rows"])}
    assert list(layers.values()) == sorted(layers.values())
    assert len(set(layers.values())) == len(layers)
    assert len(root.findall('.//s:line[@class="tick"]', NS)) == 12
    assert not root.findall('.//s:text', NS)
    assert "@keyframes" not in svg
    assert len(svg.encode()) < 400_000
    desc = root.find("s:desc", NS).text
    for value in ("1.2", "0.099", "2.5 × 10⁻⁷"):
        assert value in desc
    markers = root.findall('.//s:line[@class="median"]', NS)
    for marker, form in zip(markers, ("exact", "no_rope", "plain")):
        assert float(marker.attrib["x1"]) == pytest.approx(build.log_x(median(row[form] for row in snapshot["rows"])), abs=0.01)


def test_titles_and_medians_follow_supplied_data():
    build = builder()
    snapshot = copy.deepcopy(data())
    snapshot["rows"] = [{"layer": 0, "head": 0, "plain": 2.3, "no_rope": 0.045, "exact": 3.4e-6}]
    snapshot["config"]["model"] = "sample/model"
    root = ET.fromstring(build.render(snapshot, "light"))
    assert root.find("s:title", NS).text.startswith("1 attention heads")
    desc = root.find("s:desc", NS).text
    assert all(value in desc for value in ("model", "2.3", "0.045", "3.4 × 10⁻⁶"))


def test_shared_cli_writes_normal_and_frozen_variants(tmp_path):
    from figkit.cli import main
    def render(snapshot, mode, freeze_at=None):
        return f"{snapshot['value']}:{mode}:{freeze_at}"
    main("sample", tmp_path, render, {"value": 7}, argv=[])
    assert (tmp_path / "sample-light.svg").read_text() == "7:light:None"
    main("sample", tmp_path, render, {"value": 7}, argv=["--preview", "0,2.5"], root=tmp_path)
    assert (tmp_path / ".preview/sample-dark-2.5.svg").read_text() == "7:dark:2.5"


@pytest.mark.parametrize("times", ["-1", "nan", "inf", "bad"])
def test_shared_cli_rejects_invalid_preview_times(tmp_path, times):
    from figkit.cli import main
    with pytest.raises(SystemExit):
        main("sample", tmp_path, lambda *args, **kwargs: "", {}, argv=["--preview", times], root=tmp_path)


def test_qk_script_supports_preview():
    result = subprocess.run([str(ROOT / ".venv/bin/python"), "figures/qk/build.py", "--preview", "0"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    for mode in ("light", "dark"):
        svg = (ROOT / f".preview/qk-{mode}-0.svg").read_text()
        assert "animation-play-state:paused!important" in svg


@pytest.mark.parametrize("value, expected", [(2.5e-7, ("2.5 × 10", "−7")), (1e-8, ("10", "−8"))])
def test_power_parts_use_regular_digits_and_real_minus(value, expected):
    assert builder().power_parts(value) == expected


def test_power_run_centers_base_and_raised_exponent():
    build = builder()
    from figkit.text import Outliner
    face = build.faces()["number"]
    base, exponent = build.power_parts(2.5e-7)
    size, x, y = 15, 300, 200
    out = Outliner()
    run = build.power_run(out, face, (base, exponent), x, y, size, "middle")
    width = face.advance(base, size) + face.advance(exponent, size * 0.7)
    start = x - width / 2
    expected = out.run(face, base, start, y, size)
    expected += out.run(face, exponent, start + face.advance(base, size), y - size * 0.4, size * 0.7)
    assert run == expected


def test_plot_spacing_and_mark_visibility():
    build = builder()
    root = ET.fromstring(build.render(data(), "light"))
    geometry = build.Geometry()
    dots = root.findall('.//s:circle[@class="head"]', NS)
    ys = sorted({float(dot.attrib["cy"]) for dot in dots})
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    assert min(gaps) >= 10
    assert all(gap == pytest.approx(gaps[0]) for gap in gaps)
    assert all(dot.attrib["r"] == "3.5" and dot.attrib["opacity"] == "0.85" for dot in dots)
    from figkit.color import FAINT
    grid = root.find(f'.//s:g[@stroke="{FAINT["light"]}"]', NS)
    assert grid.attrib["opacity"] == "0.6"
    assert len(grid.findall("s:line", NS)) == 12
    ticks = root.findall('.//s:g[@class="power-tick"]', NS)
    assert len(ticks) == 12
    for tick in ticks:
        uses = tick.findall("s:use", NS)
        baseline = float(uses[0].attrib["transform"].split(")")[0].split()[-1])
        assert baseline == geometry.bottom + 18
        assert geometry.height - baseline >= 14
