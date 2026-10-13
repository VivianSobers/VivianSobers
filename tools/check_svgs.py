from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"


def check(root: Path) -> list[str]:
    paths = sorted(
        path for folder in (root / "header", root / "figures")
        for mode in ("light", "dark") for path in folder.rglob(f"*-{mode}.svg")
    )
    failures = []
    for path in paths:
        reasons = []
        mode = "light" if path.stem.endswith("-light") else "dark"
        other = "dark" if mode == "light" else "light"
        partner = path.with_name(f"{path.stem[:-len(mode)]}{other}.svg")
        if not partner.is_file():
            reasons.append(f"missing {partner.name}")
        try:
            raw = path.read_bytes()
            if len(raw) >= 400_000:
                reasons.append("must be under 400 KB")
            tree = ET.fromstring(raw)
            text = raw.decode("utf-8")
            for name in ("title", "desc"):
                element = tree.find(f"{{{SVG}}}{name}")
                if element is None or not "".join(element.itertext()).strip():
                    reasons.append(f"missing {name}")
            for name in ("script", "foreignObject"):
                if f"<{name}" in text or any(element.tag.rsplit("}", 1)[-1] == name for element in tree.iter()):
                    reasons.append(f"forbidden {name}")
            text = re.sub(r'xmlns(?::[\w.-]+)?\s*=\s*([\'"])' + re.escape(SVG) + r'\1', "", text)
            values = " ".join(
                value for element in tree.iter()
                for value in (*element.attrib.values(), element.text or "", element.tail or "")
            )
            if re.search(r"https?://", text + values, re.IGNORECASE):
                reasons.append("external URL")
        except (ET.ParseError, UnicodeError, OSError) as error:
            reasons.append(f"XML/read error: {error}")
        failures.extend(f"{path.relative_to(root)}: {reason}" for reason in reasons)
    if not failures:
        print(f"{len(paths)} SVGs checked")
    return failures


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    failures = check(root)
    for failure in failures:
        print(failure)
    sys.exit(bool(failures))
