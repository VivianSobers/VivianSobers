import argparse
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(name, here, render, data, argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=f"Draw {name} from its recorded data.")
    parser.add_argument("--preview", help="comma-separated frame times in seconds")
    args = parser.parse_args(argv)
    if args.preview is not None:
        try:
            times = [float(value) for value in args.preview.split(",")]
            if any(not math.isfinite(time) or time < 0 for time in times):
                raise ValueError
        except ValueError:
            parser.error("preview times must be finite, non-negative seconds")
        preview = root / ".preview"
        preview.mkdir(exist_ok=True)
        for mode in ("light", "dark"):
            for time in times:
                (preview / f"{name}-{mode}-{time:g}.svg").write_text(render(data, mode, freeze_at=time))
        return
    for mode in ("light", "dark"):
        (here / f"{name}-{mode}.svg").write_text(render(data, mode))
