"""Snapshot the recorded seeded triangle fit and its target."""

import argparse
import csv
import hashlib
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PATHS = [
    "docs/target.png", "crates/diffrast/src/bin/fit.rs",
    "crates/diffrast/src/fit.rs", "crates/diffrast/src/serial.rs",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=ROOT.parent / "Differentiable Rasterizer")
    parser.add_argument("--out", required=True, type=Path, help="directory written by record.sh")
    args = parser.parse_args()
    repo, run = args.repo.resolve(), args.out.resolve()
    scene = json.loads((run / "scene.json").read_text())
    with (run / "loss.csv").open() as stream:
        losses = [{"iter": int(row["iter"]), "loss": float(row["loss"])} for row in csv.DictReader(stream)]
    if len(scene["triangles"]) != 150 or not 2 <= len(losses) <= 800:
        raise ValueError("Expected 150 triangles and at most 800 completed steps")
    if any(point["iter"] != i or not math.isfinite(point["loss"]) or point["loss"] <= 0
           for i, point in enumerate(losses)):
        raise ValueError("Loss series must be positive, finite and consecutive")
    png = (run / "target.png").read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n" or len(png) > 60_000:
        raise ValueError("Target must be a PNG under 60 KB")
    width, height = struct.unpack(">II", png[16:24])
    count = min(200, len(losses))
    indices = [round(i * (len(losses) - 1) / (count - 1)) for i in range(count)]
    best = losses[0]
    for point in losses[1:]:
        if point["loss"] + 1e-7 < best["loss"]:
            best = point
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    config = {
        "target": "docs/target.png", "tris": 150, "iters": 800, "seed": 0, "out": str(run),
        "size": 192, "save_every": 0, "export": 1024, "patience": 250, "quiet": False,
        "cpu_cores": 1, "sigma_start": 0.02, "sigma_end": 0.0015,
        "lr_pos": 0.004, "lr_color": 0.02, "lr_alpha": 0.01, "min_delta": 1e-7,
        "downsample": "200 evenly spaced iteration indices, rounded; first and last retained",
        "scene": "best scene with min_delta improvement, in back-to-front paint order",
        "coordinates": "normalized image space, top-left origin; vertices may extend outside the canvas",
    }
    snapshot = {
        "source": {
            "repo": "https://github.com/VivianSobers/Differentiable-Rasterizer", "commit": commit,
            "paths": PATHS, "binary_sha256": digest(repo / "target/release/fit"),
            "command": ["target/release/fit", config["target"], "--tris", "150", "--iters", "800",
                        "--seed", "0", "--out", str(run)],
            "artifacts": {name: digest(run / name) for name in ("scene.json", "loss.csv", "target.png")},
        },
        "config": config, "background": scene["background"], "triangles": scene["triangles"],
        "target": {"width": width, "height": height, "bytes": len(png), "sha256": digest(run / "target.png")},
        "loss": [losses[i] for i in indices], "steps": len(losses),
        "first_loss": losses[0]["loss"], "last_loss": losses[-1]["loss"],
        "ratio": losses[0]["loss"] / losses[-1]["loss"],
        "best_iter": best["iter"], "best_loss": best["loss"],
    }
    shutil.copyfile(run / "target.png", HERE / "target.png")
    (HERE / "data.json").write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    print(f"Recorded {len(scene['triangles'])} triangles, {len(losses)} steps, {count} loss points")
    print(f"First/last loss: {snapshot['first_loss']:.9g} / {snapshot['last_loss']:.9g}")
    print(f"Loss fell {snapshot['ratio']:.9g}x; best scene at iteration {best['iter']}")


if __name__ == "__main__":
    main()
