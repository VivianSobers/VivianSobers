import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from figures.swipeline import build
from figkit.color import FAINT, INK, MUTED

NS = {"s": "http://www.w3.org/2000/svg"}

REQUIRED_NODES = {
    "replayer",
    "gateway",
    "PostgreSQL",
    "Flink",
    "Druid",
    "Superset",
    "Spark batch",
    "Hudi on SeaweedFS",
}

REQUIRED_TOPICS = {
    "auth.requests",
    "auth.proposals",
    "decisions.raw",
    "decisions",
    "lifecycle",
}


def point_on_rect_border(px: float, py: float, rx: float, ry: float, rw: float, rh: float, tol: float = 1.0) -> bool:
    on_left = abs(px - rx) <= tol and (ry - tol <= py <= ry + rh + tol)
    on_right = abs(px - (rx + rw)) <= tol and (ry - tol <= py <= ry + rh + tol)
    on_top = abs(py - ry) <= tol and (rx - tol <= px <= rx + rw + tol)
    on_bottom = abs(py - (ry + rh)) <= tol and (rx - tol <= px <= rx + rw + tol)
    return on_left or on_right or on_top or on_bottom


def test_canvas_geometry_and_margins():
    geom = build.Geometry()
    assert geom.width == 1280
    assert geom.height == 520
    assert geom.margin == 30


def test_nodes_and_bus_inside_canvas_with_margins():
    geom = build.Geometry()
    nodes = build.get_nodes()
    bus = build.get_bus()

    all_boxes = [(node.name, node.x, node.y, node.width, node.height) for node in nodes.values()]
    all_boxes.append((bus.name, bus.x, bus.y, bus.width, bus.height))

    for name, x, y, w, h in all_boxes:
        assert x >= geom.margin, f"{name} violates left margin: {x} < {geom.margin}"
        assert y >= geom.margin, f"{name} violates top margin: {y} < {geom.margin}"
        assert x + w <= geom.width - geom.margin, f"{name} violates right margin: {x + w} > {geom.width - geom.margin}"
        assert y + h <= geom.height - geom.margin, f"{name} violates bottom margin: {y + h} > {geom.height - geom.margin}"


def test_no_nodes_or_bus_overlap():
    nodes = build.get_nodes()
    bus = build.get_bus()

    all_boxes = list(nodes.values()) + [bus]
    for i in range(len(all_boxes)):
        for j in range(i + 1, len(all_boxes)):
            a, b = all_boxes[i], all_boxes[j]
            overlap_x = (a.x < b.x + b.width) and (a.x + a.width > b.x)
            overlap_y = (a.y < b.y + b.height) and (a.y + a.height > b.y)
            assert not (overlap_x and overlap_y), f"Elements {a.name} and {b.name} overlap"


def test_every_edge_endpoint_lies_on_node_border_or_bus():
    nodes = build.get_nodes()
    bus = build.get_bus()
    edges = build.get_edges()

    boxes = {n.name: (n.x, n.y, n.width, n.height) for n in nodes.values()}
    boxes[bus.name] = (bus.x, bus.y, bus.width, bus.height)

    for edge in edges:
        src_box = boxes[edge.source]
        assert point_on_rect_border(edge.x1, edge.y1, *src_box), (
            f"Edge {edge.source} -> {edge.target} start ({edge.x1}, {edge.y1}) "
            f"not on {edge.source} border {src_box}"
        )

        tgt_box = boxes[edge.target]
        assert point_on_rect_border(edge.x2, edge.y2, *tgt_box), (
            f"Edge {edge.source} -> {edge.target} end ({edge.x2}, {edge.y2}) "
            f"not on {edge.target} border {tgt_box}"
        )


def test_bus_topics_and_edge_attachment():
    bus = build.get_bus()
    edges = build.get_edges()

    assert set(bus.topics.keys()) == REQUIRED_TOPICS

    # Every edge attaching to the bus must attach at its topic label height
    for edge in edges:
        if edge.topic:
            assert edge.topic in bus.topics
            topic_y = bus.topics[edge.topic]
            if edge.source == bus.name:
                assert abs(edge.y1 - topic_y) <= 16, (
                    f"Edge from bus on {edge.topic} attached at y={edge.y1}, expected around {topic_y}"
                )
            if edge.target == bus.name:
                assert abs(edge.y2 - topic_y) <= 16, (
                    f"Edge to bus on {edge.topic} attached at y={edge.y2}, expected around {topic_y}"
                )


def test_required_topology():
    nodes = build.get_nodes()
    assert set(nodes.keys()) == REQUIRED_NODES

    # Subtitles on nodes
    assert nodes["PostgreSQL"].subtitle == "final decisions"
    assert nodes["Flink"].subtitle == "scoring, canonicalizing"
    assert nodes["Hudi on SeaweedFS"].subtitle == "ledger"

    # PostgreSQL directly under gateway
    assert nodes["PostgreSQL"].x == nodes["gateway"].x
    assert nodes["PostgreSQL"].y > nodes["gateway"].y + nodes["gateway"].height


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_render_svg_document_structure(mode):
    svg = build.render({}, mode)
    root = ET.fromstring(svg)

    assert root.attrib["viewBox"] == "0 0 1280 520"
    assert root.attrib["width"] == "1280"
    assert root.attrib["height"] == "520"

    title_elem = root.find("s:title", NS)
    assert title_elem is not None
    assert title_elem.text == "Card traffic through one machine's payment network"

    desc_elem = root.find("s:desc", NS)
    assert desc_elem is not None
    desc_text = desc_elem.text
    assert "PostgreSQL" in desc_text
    assert "gateway" in desc_text
    assert "Kafka" in desc_text
    assert "Flink" in desc_text
    assert "Druid" in desc_text
    assert "Superset" in desc_text
    assert "Spark" in desc_text
    assert "Hudi" in desc_text

    assert len(svg.encode("utf-8")) < 400_000
    assert "@media (prefers-reduced-motion:reduce){*{animation:none!important}}" in svg


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_render_nodes_and_styling(mode):
    svg = build.render({}, mode)
    root = ET.fromstring(svg)

    node_rects = root.findall(".//s:rect[@class='node']", NS)
    # 8 nodes + 1 bus
    assert len(node_rects) == len(REQUIRED_NODES) + 1

    for rect in node_rects:
        assert rect.attrib["stroke"] == FAINT[mode]
        assert float(rect.attrib["stroke-width"]) == 2.5
        assert float(rect.attrib["rx"]) >= 6
        assert float(rect.attrib["ry"]) >= 6
        assert rect.attrib["fill"] in ("none", "transparent")

    # Topic labels group inside the bus
    topic_group = root.find(".//s:g[@class='bus-topics']", NS)
    assert topic_group is not None
    assert topic_group.attrib["fill"] == MUTED[mode]


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_render_edges_and_arrows(mode):
    svg = build.render({}, mode)
    root = ET.fromstring(svg)

    edges_group = root.find(".//s:g[@class='edges']", NS)
    assert edges_group is not None
    edge_elements = edges_group.findall("./*")
    assert len(edge_elements) == len(build.get_edges())

    for elem in edge_elements:
        assert elem.attrib["stroke"] == MUTED[mode]
        assert float(elem.attrib["stroke-width"]) == 2.5
        assert "marker-end" in elem.attrib


def test_render_supports_freeze_at():
    svg_frozen = build.render({}, "light", freeze_at=2.0)
    assert "*{animation-play-state:paused!important}" in svg_frozen


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_animation_loop_and_keyframes(mode):
    svg = build.render({}, mode)
    root = ET.fromstring(svg)
    style = root.find("s:style", NS).text
    assert "14s" in style
    assert "offset-path" not in style
    assert "@keyframes" in style
    assert "translate" in style


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_animated_dots_specification(mode):
    from figkit.color import BLUE, EMBER
    svg = build.render({}, mode)
    root = ET.fromstring(svg)

    # BLUE moving dots (r 6)
    blue_dots = root.findall(f".//s:circle[@fill='{BLUE[mode]}']", NS)
    assert len(blue_dots) >= 1
    for d in blue_dots:
        if d.attrib.get("class") == "faint-dot":
            continue
        assert float(d.attrib["r"]) == 6.0

    # EMBER proposal dot (r 6)
    ember_dots = root.findall(f".//s:circle[@fill='{EMBER[mode]}']", NS)
    assert len(ember_dots) >= 1
    assert any(float(d.attrib["r"]) == 6.0 for d in ember_dots)

    # Continuous fainter dots
    faint_dots = root.findall(".//s:circle[@class='faint-dot']", NS)
    assert len(faint_dots) >= 2
    assert all(float(d.attrib["r"]) >= 5.0 for d in faint_dots)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_late_proposal_refused_label(mode):
    from figkit.color import EMBER
    svg = build.render({}, mode)
    root = ET.fromstring(svg)
    label_group = root.find(".//s:g[@class='late-proposal-label']", NS)
    assert label_group is not None
    assert label_group.attrib["fill"] == EMBER[mode]


def test_settled_dots_at_postgresql():
    svg = build.render({}, "light")
    root = ET.fromstring(svg)
    settled = root.findall(".//s:circle[@class='settled-dot']", NS)
    assert len(settled) >= 1
    nodes = build.get_nodes()
    pg = nodes["PostgreSQL"]
    for dot in settled:
        cx = float(dot.attrib["cx"])
        cy = float(dot.attrib["cy"])
        assert pg.x <= cx <= pg.x + pg.width
        assert pg.y <= cy <= pg.y + pg.height
    # Dots settling in PostgreSQL must stop inside the box away from its text
    assert len(settled) == 2
    # Arranged at left edge away from text
    assert all(float(d.attrib["cx"]) < pg.x + 40 for d in settled)
    # Short stack: same cx, different cy
    cxs = [float(d.attrib["cx"]) for d in settled]
    cys = [float(d.attrib["cy"]) for d in settled]
    assert cxs[0] == pytest.approx(cxs[1], abs=1.0)
    assert abs(cys[0] - cys[1]) >= 12


def test_desc_includes_animation_details():
    svg = build.render({}, "light")
    root = ET.fromstring(svg)
    desc = root.find("s:desc", NS).text
    assert "14 s" in desc or "14s" in desc or "14-second" in desc
    assert "late proposal" in desc


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
    build.render({}, mode, freeze_at=13)
    assert runs[0][1] == 26
    assert runs[1][1] == 18
    assert all(size >= 16 for _, size, _ in runs)
    geom = build.Geometry()
    for text, _, (left, top, right, bottom) in runs:
        assert 30 <= left < right <= 1250, text
        assert 0 <= top < bottom <= geom.height - 10, text
    for index, (text, _, box) in enumerate(runs):
        for other, _, next_box in runs[index + 1:]:
            assert (box[2] + 2 <= next_box[0] or next_box[2] + 2 <= box[0]
                    or box[3] + 2 <= next_box[1] or next_box[3] + 2 <= box[1]), (text, other)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_marks_scale_with_the_larger_labels(mode):
    root = ET.fromstring(build.render({}, mode))
    for rect in root.findall(".//s:rect[@class='node']", NS):
        assert float(rect.attrib["stroke-width"]) == 2.5
    for path in root.findall(".//s:path[@class='edge']", NS):
        assert float(path.attrib["stroke-width"]) == 2.5
    for dot in root.findall(".//s:circle", NS):
        assert float(dot.attrib["r"]) >= 5.0
    transit_dots = root.findall(".//s:circle[@class='transit-dot']", NS)
    assert all(float(d.attrib["r"]) == 6.0 for d in transit_dots)
    settled_dots = root.findall(".//s:circle[@class='settled-dot']", NS)
    assert all(float(d.attrib["r"]) == 6.0 for d in settled_dots)
    late_dots = root.findall(".//s:circle[@class='late-proposal-dot']", NS)
    assert all(float(d.attrib["r"]) == 6.0 for d in late_dots)
    for marker in root.findall(".//s:marker", NS):
        assert float(marker.attrib["markerWidth"]) >= 10.0
        assert float(marker.attrib["markerHeight"]) >= 10.0
