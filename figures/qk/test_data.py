import json
import math
import re
from pathlib import Path
from statistics import median

import pytest

HERE = Path(__file__).resolve().parent


def snapshot():
    path = HERE / "data.json"
    assert path.is_file(), "per-head score snapshot is missing"
    return json.loads(path.read_text())


def test_snapshot_has_every_layer_and_head_once():
    rows = snapshot()["rows"]
    assert len(rows) == 448
    assert {(row["layer"], row["head"]) for row in rows} == {
        (layer, head) for layer in range(28) for head in range(16)
    }
    for row in rows:
        assert set(row) == {"layer", "head", "plain", "no_rope", "exact"}
        assert all(math.isfinite(row[key]) and row[key] > 0 for key in ("plain", "no_rope", "exact"))


@pytest.mark.parametrize("form,expected", [("exact", "2.5e-07"), ("no_rope", "0.099"), ("plain", "1.2")])
def test_snapshot_medians_to_two_significant_figures(form, expected):
    assert format(median(row[form] for row in snapshot()["rows"]), ".2g") == expected


def test_snapshot_records_source_and_run_config():
    data = snapshot()
    assert data["source"]["repo"] == "https://github.com/VivianSobers/qk-attribution"
    assert re.fullmatch(r"[0-9a-f]{40}", data["source"]["commit"])
    assert data["source"]["paths"] == ["experiments/results/003-qk-form-qwen3-0.6b.json"]
    assert data["config"] == {
        "model": "Qwen/Qwen3-0.6B",
        "prompt": "The Eiffel Tower is located in the city of Paris, the capital of France.",
        "seed": 0,
        "seq": 18,
    }


def test_snapshot_keeps_rel_fro_precision_and_uses_derived_form():
    row = next(row for row in snapshot()["rows"] if (row["layer"], row["head"]) == (0, 0))
    assert row == {
        "layer": 0,
        "head": 0,
        "plain": 0.9741496443748474,
        "no_rope": 0.1585138589143753,
        "exact": 2.9896963837927615e-07,
    }
