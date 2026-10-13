import hashlib
import json
import math
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent


def snapshot():
    path = HERE / "data.json"
    assert path.is_file(), "seeded triangle fit snapshot is missing"
    return json.loads(path.read_text())


def test_snapshot_has_150_triangles_in_paint_order():
    data = snapshot()
    assert len(data["triangles"]) == data["config"]["tris"] == 150
    assert len(data["background"]) == 3
    assert all(0 <= value <= 1 for value in data["background"])
    for triangle in data["triangles"]:
        assert set(triangle) == {"verts", "color", "alpha"}
        assert len(triangle["verts"]) == 3
        assert all(len(vertex) == 2 for vertex in triangle["verts"])
        assert all(math.isfinite(value) for vertex in triangle["verts"] for value in vertex)
        assert len(triangle["color"]) == 3
        assert all(0 <= value <= 1 for value in triangle["color"])
        assert 0 <= triangle["alpha"] <= 1


def test_loss_series_keeps_endpoints_and_ratio():
    data = snapshot()
    loss = data["loss"]
    assert 2 <= len(loss) <= 200
    assert loss[0] == {"iter": 0, "loss": data["first_loss"]}
    assert loss[-1] == {"iter": data["steps"] - 1, "loss": data["last_loss"]}
    assert data["config"]["iters"] == 800
    assert data["steps"] == 797
    assert all(math.isfinite(point["loss"]) and point["loss"] > 0 for point in loss)
    assert all(a["iter"] < b["iter"] for a, b in zip(loss, loss[1:]))
    assert data["ratio"] == data["first_loss"] / data["last_loss"] > 1
    assert data["best_loss"] <= data["last_loss"]
    assert 0 <= data["best_iter"] < data["steps"]


def test_config_records_every_cli_option():
    config = snapshot()["config"]
    assert {key: config[key] for key in (
        "tris", "iters", "seed", "size", "save_every", "export", "patience", "quiet",
    )} == {
        "tris": 150, "iters": 800, "seed": 0, "size": 192,
        "save_every": 0, "export": 1024, "patience": 250, "quiet": False,
    }
    assert config["target"] == "docs/target.png"
    assert Path(config["out"]).is_absolute()
    assert config["cpu_cores"] == 1


def test_target_is_small_png_with_recorded_dimensions_and_hash():
    data = snapshot()
    png = (HERE / "target.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) <= 60_000
    assert struct.unpack(">II", png[16:24]) == (176, 176)
    assert data["target"] == {
        "width": 176, "height": 176, "bytes": len(png),
        "sha256": hashlib.sha256(png).hexdigest(),
    }


def test_source_records_commit_command_and_raw_artifacts():
    source = snapshot()["source"]
    assert source["repo"] == "https://github.com/VivianSobers/Differentiable-Rasterizer"
    assert re.fullmatch(r"[0-9a-f]{40}", source["commit"])
    assert re.fullmatch(r"[0-9a-f]{64}", source["binary_sha256"])
    assert source["paths"] == [
        "docs/target.png", "crates/diffrast/src/bin/fit.rs",
        "crates/diffrast/src/fit.rs", "crates/diffrast/src/serial.rs",
    ]
    assert set(source["artifacts"]) == {"scene.json", "loss.csv", "target.png"}
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in source["artifacts"].values())
    config = snapshot()["config"]
    assert source["command"][1:] == [
        config["target"], "--tris", "150", "--iters", "800", "--seed", "0", "--out", config["out"],
    ]
