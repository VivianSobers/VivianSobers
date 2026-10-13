"""Draw swipeline data path."""

import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from figkit.cli import main
from figkit.color import CATEGORICAL, STATUS, FAINT, INK, MUTED
from figkit.svg import delay, document
from figkit.text import Face, Outliner

HERE = Path(__file__).resolve().parent
TOPIC_HUES = {
    "auth.requests": "blue", "auth.proposals": "blue",
    "decisions.raw": "aqua", "decisions": "aqua", "lifecycle": "orange",
}
NODE_HUES = {
    "replayer": ("blue",), "PostgreSQL": ("blue",), "Flink": ("blue", "aqua"),
    "Druid": ("aqua",), "Superset": ("aqua",),
    "Spark batch": ("orange",), "Hudi on SeaweedFS": ("orange",),
}


@dataclass(frozen=True)
class Geometry:
    width: float = 1280
    height: float = 520
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
        "replayer": Node("replayer", 60, 150, 180, 56),
        "gateway": Node("gateway", 300, 146, 210, 64),
        "PostgreSQL": Node("PostgreSQL", 300, 350, 210, 80, subtitle="final decisions"),
        "Flink": Node("Flink", 770, 146, 240, 64, subtitle="scoring, canonicalizing"),
        "Druid": Node("Druid", 860, 312, 140, 56),
        "Superset": Node("Superset", 1060, 312, 160, 56),
        "Spark batch": Node("Spark batch", 860, 397, 140, 56),
        "Hudi on SeaweedFS": Node("Hudi on SeaweedFS", 1050, 393, 190, 64, subtitle="ledger"),
    }


def get_bus() -> Bus:
    return Bus(
        "Kafka",
        560,
        110,
        160,
        360,
        topics={
            "auth.requests": 175,
            "auth.proposals": 205,
            "decisions.raw": 280,
            "decisions": 340,
            "lifecycle": 425,
        },
    )


def get_edges() -> list[Edge]:
    return [
        Edge("replayer", "gateway", 240, 178, 300, 178),
        Edge("gateway", "Kafka", 510, 175, 560, 175, topic="auth.requests"),
        Edge("Kafka", "Flink", 720, 175, 770, 175, topic="auth.requests"),
        Edge("Flink", "Kafka", 770, 205, 720, 205, topic="auth.proposals"),
        Edge("Kafka", "gateway", 560, 205, 510, 205, topic="auth.proposals"),
        Edge("gateway", "PostgreSQL", 325, 210, 325, 350),
        Edge(
            "PostgreSQL",
            "Kafka",
            450,
            350,
            560,
            280,
            topic="decisions.raw",
            path="M 450 350 L 450 286 A 6 6 0 0 1 456 280 L 560 280",
        ),
        Edge(
            "Kafka",
            "Flink",
            720,
            280,
            810,
            210,
            topic="decisions.raw",
            path="M 720 280 L 804 280 A 6 6 0 0 0 810 274 L 810 210",
        ),
        Edge(
            "Flink",
            "Kafka",
            850,
            210,
            720,
            334,
            topic="decisions",
            path="M 850 210 L 850 328 A 6 6 0 0 1 844 334 L 720 334",
        ),
        Edge("Kafka", "Druid", 720, 346, 860, 346, topic="decisions"),
        Edge("Druid", "Superset", 1000, 346, 1060, 346),
        Edge("PostgreSQL", "Kafka", 510, 425, 560, 425, topic="lifecycle"),
        Edge("Kafka", "Spark batch", 720, 425, 860, 425, topic="lifecycle"),
        Edge("Spark batch", "Hudi on SeaweedFS", 1000, 425, 1050, 425),
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
    heading = out.run(face["title"], title, 40, 48, 26)
    subline = out.run(face["body"], subtitle, 40, 78, 18)

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
            f'fill="none" stroke="{FAINT[mode]}" stroke-width="2.5"/>'
        )
        hues = NODE_HUES.get(node.name, ())
        for index, hue in enumerate(hues):
            width = (node.width - 2 * node.rx) / len(hues)
            node_elements.append(
                f'<rect class="node-accent" aria-label="{node.name}" '
                f'x="{node.x + node.rx + index * width:g}" y="{node.y:g}" '
                f'width="{width:g}" height="2" fill="{CATEGORICAL[hue][mode]}"/>'
            )
        if node.name == "PostgreSQL":
            text_cx = node.x + 35 + (node.width - 35) / 2
            node_names.append(
                out.run(face["body"], node.name, text_cx, node.cy - 6, 16, anchor="middle")
            )
            node_subtitles.append(
                out.run(face["body"], node.subtitle, text_cx, node.cy + 18, 16, anchor="middle")
            )
        elif node.subtitle:
            node_names.append(
                out.run(face["body"], node.name, node.cx, node.cy - 6, 16, anchor="middle")
            )
            node_subtitles.append(
                out.run(face["body"], node.subtitle, node.cx, node.cy + 18, 16, anchor="middle")
            )
        else:
            node_names.append(
                out.run(face["body"], node.name, node.cx, node.cy + 5, 16, anchor="middle")
            )

    # Kafka bus
    node_elements.append(
        f'<rect class="node" x="{bus.x:g}" y="{bus.y:g}" '
        f'width="{bus.width:g}" height="{bus.height:g}" rx="{bus.rx:g}" ry="{bus.ry:g}" '
        f'fill="none" stroke="{FAINT[mode]}" stroke-width="2.5"/>'
    )
    bus_label = out.run(face["body"], bus.name, bus.cx, bus.y + 28, 17, anchor="middle")

    bus_topics = []
    for topic, topic_y in bus.topics.items():
        bus_topics.append(
            f'<g aria-label="{topic}" fill="{CATEGORICAL[TOPIC_HUES[topic]][mode]}">'
            f'{out.run(face["number"], topic, bus.cx, topic_y + 5, 16, anchor="middle")}</g>'
        )

    markers = "".join(
        f'<marker id="arrow-{hue}-{mode}" viewBox="0 0 10 10" refX="7" refY="5" '
        f'markerWidth="10" markerHeight="10" orient="auto" markerUnits="userSpaceOnUse">'
        f'<path d="M 1 2 L 7 5 L 1 8 z" fill="{CATEGORICAL[hue][mode]}"/></marker>'
        for hue in ("blue", "aqua", "orange")
    )

    defs = out.defs() + markers

    edge_elements = []
    for edge in edges:
        hue = TOPIC_HUES[edge.topic] if edge.topic else NODE_HUES.get(edge.source, ("blue",))[0]
        edge_elements.append(
            f'<path class="edge" d="{edge.path_d()}" stroke="{CATEGORICAL[hue][mode]}" stroke-width="2.5" '
            f'fill="none" stroke-linecap="round" marker-end="url(#arrow-{hue}-{mode})"/>'
        )

    frozen = delay(0, freeze_at)

    dots = []

    # Transaction 1
    dots.append(
        f'<circle class="transit-dot" cx="240" cy="178" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t1_seg1 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="transit-dot" cx="510" cy="175" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t1_seg2 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="transit-dot" cx="720" cy="175" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t1_seg3 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="transit-dot" cx="770" cy="205" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t1_seg4 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="transit-dot" cx="560" cy="205" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t1_seg5 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="settled-dot" cx="325" cy="375" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t1_settle 14s linear infinite;{frozen}"/>'
    )

    # Transaction 2
    dots.append(
        f'<circle class="transit-dot" cx="240" cy="178" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t2_seg1 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="transit-dot" cx="510" cy="175" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t2_seg2 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="transit-dot" cx="720" cy="175" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t2_seg3 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="settled-dot" cx="325" cy="405" r="6" fill="{CATEGORICAL["blue"][mode]}" style="animation:t2_settle 14s linear infinite;{frozen}"/>'
    )

    # Transaction 2 late proposal
    dots.append(
        f'<circle class="transit-dot" cx="770" cy="205" r="6" fill="{STATUS["critical"]}" style="animation:t2_prop_seg4 14s linear infinite;{frozen}"/>'
    )
    dots.append(
        f'<circle class="late-proposal-dot" cx="560" cy="205" r="6" fill="{STATUS["critical"]}" style="animation:late_proposal_dot 14s linear infinite;{frozen}"/>'
    )

    # Continuous fainter dots on downstream paths (r 5)
    for i in range(4):
        d_offset = delay(i * 0.875, freeze_at)
        dots.append(
            f'<circle class="faint-dot" cx="720" cy="346" r="5" fill="{CATEGORICAL["aqua"][mode]}" style="animation:flow_dec_1 3.5s linear infinite;{d_offset}"/>'
        )
        dots.append(
            f'<circle class="faint-dot" cx="1000" cy="346" r="5" fill="{CATEGORICAL["aqua"][mode]}" style="animation:flow_dec_2 3.5s linear infinite;{d_offset}"/>'
        )

        l_offset = delay(i * 0.875 + 0.4375, freeze_at)
        dots.append(
            f'<circle class="faint-dot" cx="720" cy="425" r="5" fill="{CATEGORICAL["orange"][mode]}" style="animation:flow_life_1 3.5s linear infinite;{l_offset}"/>'
        )
        dots.append(
            f'<circle class="faint-dot" cx="1000" cy="425" r="5" fill="{CATEGORICAL["orange"][mode]}" style="animation:flow_life_2 3.5s linear infinite;{l_offset}"/>'
        )

    # Late proposal refused label
    late_label_glyphs = out.run(face["body"], "late proposal refused", 435, 240, 16, anchor="middle")
    late_label_elem = (
        f'<g class="late-proposal-label" fill="{STATUS["critical"]}" style="animation:late_label 14s linear infinite;{frozen}">{late_label_glyphs}</g>'
    )

    css = (
        ".transit-dot{opacity:0}"
        ".settled-dot{opacity:1}"
        ".late-proposal-dot{opacity:0;animation:late_proposal_dot 14s linear infinite}"
        ".late-proposal-label{opacity:0;animation:late_label 14s linear infinite}"
        ".faint-dot{opacity:0}"
        ".t1-seg1{animation:t1_seg1 14s linear infinite}"
        ".t1-seg2{animation:t1_seg2 14s linear infinite}"
        ".t1-seg3{animation:t1_seg3 14s linear infinite}"
        ".t1-seg4{animation:t1_seg4 14s linear infinite}"
        ".t1-seg5{animation:t1_seg5 14s linear infinite}"
        ".t2-seg1{animation:t2_seg1 14s linear infinite}"
        ".t2-seg2{animation:t2_seg2 14s linear infinite}"
        ".t2-seg3{animation:t2_seg3 14s linear infinite}"
        ".t2-prop-seg4{animation:t2_prop_seg4 14s linear infinite}"
        "@keyframes t1_seg1{0%{opacity:1;transform:translateX(0)}5.714%{opacity:1;transform:translateX(60px)}5.715%,100%{opacity:0;transform:translateX(60px)}}"
        "@keyframes t1_seg2{0%,7.143%{opacity:0;transform:translateX(0)}7.144%{opacity:1;transform:translateX(0)}11.429%{opacity:1;transform:translateX(50px)}11.430%,100%{opacity:0;transform:translateX(50px)}}"
        "@keyframes t1_seg3{0%,12.857%{opacity:0;transform:translateX(0)}12.858%{opacity:1;transform:translateX(0)}16.429%{opacity:1;transform:translateX(50px)}16.430%,100%{opacity:0;transform:translateX(50px)}}"
        "@keyframes t1_seg4{0%,20.000%{opacity:0;transform:translateX(0)}20.001%{opacity:1;transform:translateX(0)}23.571%{opacity:1;transform:translateX(-50px)}23.572%,100%{opacity:0;transform:translateX(-50px)}}"
        "@keyframes t1_seg5{0%,25.000%{opacity:0;transform:translateX(0)}25.001%{opacity:1;transform:translateX(0)}29.286%{opacity:1;transform:translateX(-50px)}29.287%,100%{opacity:0;transform:translateX(-50px)}}"
        "@keyframes t1_settle{0%,30.714%{opacity:0;transform:translateY(-165px)}30.715%{opacity:1;transform:translateY(-165px)}37.143%{opacity:1;transform:translateY(0)}96.000%{opacity:1;transform:translateY(0)}96.001%,100%{opacity:0;transform:translateY(0)}}"
        "@keyframes t2_seg1{0%,40.000%{opacity:0;transform:translateX(0)}40.001%{opacity:1;transform:translateX(0)}45.714%{opacity:1;transform:translateX(60px)}45.715%,100%{opacity:0;transform:translateX(60px)}}"
        "@keyframes t2_seg2{0%,47.143%{opacity:0;transform:translateX(0)}47.144%{opacity:1;transform:translateX(0)}51.429%{opacity:1;transform:translateX(50px)}51.430%,100%{opacity:0;transform:translateX(50px)}}"
        "@keyframes t2_seg3{0%,52.857%{opacity:0;transform:translateX(0)}52.858%{opacity:1;transform:translateX(0)}56.429%{opacity:1;transform:translateX(50px)}56.430%,100%{opacity:0;transform:translateX(50px)}}"
        "@keyframes t2_settle{0%,57.857%{opacity:0;transform:translateY(-195px)}57.858%{opacity:1;transform:translateY(-195px)}64.286%{opacity:1;transform:translateY(0)}96.000%{opacity:1;transform:translateY(0)}96.001%,100%{opacity:0;transform:translateY(0)}}"
        "@keyframes t2_prop_seg4{0%,60.714%{opacity:0;transform:translateX(0)}60.715%{opacity:1;transform:translateX(0)}64.286%{opacity:1;transform:translateX(-50px)}64.287%,100%{opacity:0;transform:translateX(-50px)}}"
        "@keyframes late_proposal_dot{0%,65.714%{opacity:0;transform:translateX(0)}65.715%{opacity:1;transform:translateX(0)}70.000%{opacity:1;transform:translateX(-50px)}80.000%{opacity:1;transform:translateX(-50px)}84.286%{opacity:0;transform:translateX(-50px)}84.287%,100%{opacity:0;transform:translateX(-50px)}}"
        "@keyframes late_label{0%,69.999%{opacity:0}70.000%{opacity:1}80.000%{opacity:1}84.286%{opacity:0}84.287%,100%{opacity:0}}"
        "@keyframes flow_dec_1{0%{opacity:0.45;transform:translateX(0)}37.143%{opacity:0.45;transform:translateX(140px)}37.144%,100%{opacity:0;transform:translateX(140px)}}"
        "@keyframes flow_dec_2{0%,42.857%{opacity:0;transform:translateX(0)}42.858%{opacity:0.45;transform:translateX(0)}62.857%{opacity:0.45;transform:translateX(60px)}62.858%,100%{opacity:0;transform:translateX(60px)}}"
        "@keyframes flow_life_1{0%{opacity:0.45;transform:translateX(0)}37.143%{opacity:0.45;transform:translateX(140px)}37.144%,100%{opacity:0;transform:translateX(140px)}}"
        "@keyframes flow_life_2{0%,42.857%{opacity:0;transform:translateX(0)}42.858%{opacity:0.45;transform:translateX(0)}60.000%{opacity:0.45;transform:translateX(50px)}60.001%,100%{opacity:0;transform:translateX(50px)}}"
    )

    body = (
        f'<g fill="{INK[mode]}">{heading}</g>'
        f'<g fill="{MUTED[mode]}">{subline}</g>'
        f'<g class="edges">{"".join(edge_elements)}</g>'
        f'<g class="dots">{"".join(dots)}</g>'
        f'<g class="nodes">{"".join(node_elements)}</g>'
        f'<g class="node-names" fill="{INK[mode]}">{bus_label}{"".join(node_names)}</g>'
        f'<g class="node-subtitles" fill="{MUTED[mode]}">{"".join(node_subtitles)}</g>'
        f'<g class="bus-topics" fill="{MUTED[mode]}">{"".join(bus_topics)}</g>'
        f'{late_label_elem}'
    )

    desc = (
        f"{title}. {subtitle} "
        "In a 14 s loop, blue dots travel replayer to gateway, through Kafka auth.requests to Flink, "
        "and return through Kafka auth.proposals to the gateway and PostgreSQL, where they settle. "
        "Continuous fainter aqua dots flow along decisions through Druid to Superset and orange dots along lifecycle through Spark to Hudi on SeaweedFS. "
        "Once per loop one scoring proposal is critical red and arrives after its transaction's decision is stored: "
        "it stops at the gateway with a late proposal refused label that fades after 2 s."
    )

    return document(
        geometry.width,
        geometry.height,
        title,
        desc,
        css,
        defs,
        body,
        freeze_at=freeze_at,
    )


if __name__ == "__main__":
    main("swipeline", HERE, render, {})
