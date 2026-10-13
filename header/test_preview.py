import json
from pathlib import Path
import sys

import build


def test_preview_cli_writes_frozen_pairs_without_changing_normal_outputs(tmp_path, monkeypatch):
    data = json.loads((Path(build.__file__).parent / "attention.json").read_text())
    header = tmp_path / "header"
    header.mkdir()
    (header / "attention.json").write_text(json.dumps(data))
    readme = tmp_path / "README.md"
    readme.write_text("<!-- header:start -->\nkeep\n<!-- header:end -->")
    for mode in ("light", "dark"):
        (header / f"heads-{mode}.svg").write_text("keep")
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "HERE", header)
    monkeypatch.setattr(sys, "argv", ["build.py", "--preview", "0,6.5"])
    build.main()
    for mode in ("light", "dark"):
        for time in (0, 6.5):
            svg = (tmp_path / ".preview" / f"heads-{mode}-{time:g}.svg").read_text()
            assert svg == build.render(data, mode, freeze_at=time)
        assert (header / f"heads-{mode}.svg").read_text() == "keep"
    assert readme.read_text() == "<!-- header:start -->\nkeep\n<!-- header:end -->"
