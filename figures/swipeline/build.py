"""Draw swipeline data path."""

import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import FAINT, INK, MUTED
from figkit.svg import document
from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Geometry:
    width: float = 1280
    height: float = 440
    margin: float = 30


@dataclass(frozen=True)
class Node:
    name: str
    x: float
    y: float
    width: float
    height: float
    subtitle: str = ""
    rx: float = 8
    ry: float = 8

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


@dataclass(frozen=True)
class Bus:
    name: str
    x: float
    y: float
    width: float
    height: float
    topics: dict[str, float]
    rx: float = 8
    ry: float = 8

    @property
    def cx(self) -> float:
        return self.x + self.width / 2


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    x1: float
    y1: float
    x2: float
    y2: float
    topic: str = ""
    path: str = ""

    def path_d(self) -> str:
        if self.path:
            return self.path
        return f"M {self.x1:g} {self.y1:g} L {self.x2:g} {self.y2:g}"


def get_nodes() -> dict[str, Node]:
    return {
        "replayer": Node("replayer", 60, 127, 160, 46),
        "gateway": Node("gateway", 320, 126, 180, 48),
        "PostgreSQL": Node("PostgreSQL", 320, 300, 180, 56, subtitle="final decisions"),
        "Flink": Node("Flink", 760, 123, 220, 54, subtitle="scoring, canonicalizing"),
        "Druid": Node("Druid", 860, 245, 140, 46),
        "Superset": Node("Superset", 1070, 245, 150, 46),
        "Spark batch": Node("Spark batch", 860, 332, 140, 46),
        "Hudi on SeaweedFS": Node("Hudi on SeaweedFS", 1060, 328, 180, 54, subtitle="ledger"),
    }


def get_bus() -> Bus:
    return Bus(
        "Kafka",
        580,
        100,
        120,
        308,
        topics={
            "auth.requests": 140,
            "auth.proposals": 170,
            "decisions.raw": 215,
            "decisions": 260,
            "lifecycle": 355,
        },
    )


def get_edges() -> list[Edge]:
    return [
        Edge("replayer", "gateway", 220, 150, 320, 150),
        Edge("gateway", "Kafka", 500, 140, 580, 140, topic="auth.requests"),
        Edge("Kafka", "Flink", 700, 140, 760, 140, topic="auth.requests"),
        Edge("Flink", "Kafka", 760, 170, 700, 170, topic="auth.proposals"),
        Edge("Kafka", "gateway", 580, 170, 500, 170, topic="auth.proposals"),
        Edge("gateway", "PostgreSQL", 380, 174, 380, 300),
        Edge(
            "PostgreSQL",
            "Kafka",
            460,
            300,
            580,
            215,
            topic="decisions.raw",
            path="M 460 300 L 460 221 A 6 6 0 0 1 466 215 L 580 215",
        ),
        Edge(
            "Kafka",
            "Flink",
            700,
            215,
            790,
            177,
            topic="decisions.raw",
            path="M 700 215 L 784 215 A 6 6 0 0 0 790 209 L 790 177",
        ),
        Edge(
            "Flink",
            "Kafka",
            830,
            177,
            700,
            254,
            topic="decisions",
            path="M 830 177 L 830 248 A 6 6 0 0 1 824 254 L 700 254",
        ),
        Edge("Kafka", "Druid", 700, 266, 860, 266, topic="decisions"),
        Edge("Druid", "Superset", 1000, 268, 1070, 268),
        Edge("PostgreSQL", "Kafka", 500, 355, 580, 355, topic="lifecycle"),
        Edge("Kafka", "Spark batch", 700, 355, 860, 355, topic="lifecycle"),
        Edge("Spark batch", "Hudi on SeaweedFS", 1000, 355, 1060, 355),
    ]


@cache
def faces() -> dict[str, Face]:
    fonts = ROOT / "figkit" / "fonts"
    return {
        "title": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 600}),
        "body": Face(fonts / "MonaSansVF[wdth,opsz,wght].ttf", {"wdth": 100, "wght": 430}),
        "number": Face(fonts / "MonaspaceNeonVar.ttf", {"wght": 400}),
    }


def render(data: dict | None = None, mode: str = "light", freeze_at: float | None = None) -> str:
    geometry = Geometry()
    title = "Card traffic through one machine's payment network"
    subtitle = "PostgreSQL holds the final decision. A scoring proposal that misses its deadline cannot change it."

    face, out = faces(), Outliner()
    heading = out.run(face["title"], title, 40, 44, 22)
    subline = out.run(face["body"], subtitle, 40, 70, 15)

    nodes = get_nodes()
    bus = get_bus()
    edges = get_edges()

    node_elements = []
    node_names = []
    node_subtitles = []

    # Regular nodes
    for node in nodes.values():
        node_elements.append(
            f'<rect class="node" x="{node.x:g}" y="{node.y:g}" '
            f'width="{node.width:g}" height="{node.height:g}" rx="{node.rx:g}" ry="{node.ry:g}" '
            f'fill="none" stroke="{FAINT[mode]}" stroke-width="1.5"/>'
        )
        if node.subtitle:
            node_names.append(
                out.run(face["body"], node.name, node.cx, node.cy - 4, 15, anchor="middle")
            )
            node_subtitles.append(
                out.run(face["body"], node.subtitle, node.cx, node.cy + 15, 13, anchor="middle")
            )
        else:
            node_names.append(
                out.run(face["body"], node.name, node.cx, node.cy + 5, 15, anchor="middle")
            )

    # Kafka bus
    node_elements.append(
        f'<rect class="node" x="{bus.x:g}" y="{bus.y:g}" '
        f'width="{bus.width:g}" height="{bus.height:g}" rx="{bus.rx:g}" ry="{bus.ry:g}" '
        f'fill="none" stroke="{FAINT[mode]}" stroke-width="1.5"/>'
    )
    bus_label = out.run(face["body"], bus.name, bus.cx, bus.y + 24, 15, anchor="middle")

    bus_topics = []
    for topic, topic_y in bus.topics.items():
        bus_topics.append(
            out.run(face["number"], topic, bus.cx, topic_y + 4, 12, anchor="middle")
        )

    marker_id = f"arrow-{mode}"
    defs = (
        f'{out.defs()}'
        f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="7" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto" markerUnits="userSpaceOnUse">'
        f'<path d="M 1 2 L 7 5 L 1 8 z" fill="{MUTED[mode]}"/>'
        f'</marker>'
    )

    edge_elements = []
    for edge in edges:
        edge_elements.append(
            f'<path class="edge" d="{edge.path_d()}" stroke="{MUTED[mode]}" stroke-width="1.5" '
            f'fill="none" stroke-linecap="round" marker-end="url(#{marker_id})"/>'
        )

    body = (
        f'<g fill="{INK[mode]}">{heading}</g>'
        f'<g fill="{MUTED[mode]}">{subline}</g>'
        f'<g class="edges">{"".join(edge_elements)}</g>'
        f'<g class="nodes">{"".join(node_elements)}</g>'
        f'<g class="node-names" fill="{INK[mode]}">{bus_label}{"".join(node_names)}</g>'
        f'<g class="node-subtitles" fill="{MUTED[mode]}">{"".join(node_subtitles)}</g>'
        f'<g class="bus-topics" fill="{MUTED[mode]}">{"".join(bus_topics)}</g>'
    )

    desc = (
        f"{title}. {subtitle} "
        "Card traffic flows from the replayer to the gateway and PostgreSQL. "
        "The gateway relay publishes from PostgreSQL to Kafka topics auth.requests, decisions.raw, and lifecycle. "
        "Flink scores auth.requests into auth.proposals consumed by the gateway. "
        "Flink also canonicalizes decisions.raw into decisions for Druid and Superset. "
        "Spark batch reads lifecycle to write Hudi ledger tables on SeaweedFS."
    )

    return document(
        geometry.width,
        geometry.height,
        title,
        desc,
        "",
        defs,
        body,
        freeze_at=freeze_at,
    )


if __name__ == "__main__":
    main("swipeline", HERE, render, {})
