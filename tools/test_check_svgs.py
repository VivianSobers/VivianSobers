from pathlib import Path
import subprocess
import sys

import pytest

CHECK = Path(__file__).with_name("check_svgs.py")
GOOD = '<svg xmlns="http://www.w3.org/2000/svg"><title>Cells</title><desc>Recorded weights</desc></svg>'


def run_check(root):
    return subprocess.run([sys.executable, str(CHECK), str(root)], capture_output=True, text=True)


def pair(root, text=GOOD, directory="header"):
    folder = root / directory
    folder.mkdir(parents=True, exist_ok=True)
    for mode in ("light", "dark"):
        (folder / f"cells-{mode}.svg").write_text(text)
    return folder


def test_good_pairs_in_header_and_nested_figures_pass(tmp_path):
    pair(tmp_path)
    pair(tmp_path, directory="figures/cells")
    result = run_check(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 SVGs checked" in result.stdout


@pytest.mark.parametrize("text,reason", [
    ("<svg>", "XML"),
    (GOOD.replace("<title>Cells</title>", ""), "title"),
    (GOOD.replace("<desc>Recorded weights</desc>", ""), "desc"),
    (GOOD.replace("</svg>", "<script/></svg>"), "script"),
    (GOOD.replace("</svg>", "<!-- <script/> --></svg>"), "script"),
    (GOOD.replace("</svg>", "<foreignObject/></svg>"), "foreignObject"),
    (GOOD.replace("</svg>", '<image href="https://example.test/image.png"/></svg>'), "URL"),
    (GOOD.replace("</svg>", '<style>path{fill:url(http://example.test/fill)}</style></svg>'), "URL"),
    (GOOD.replace("</svg>", '<image href="http://www.w3.org/2000/svg"/></svg>'), "URL"),
    (GOOD.replace("</svg>", " " * 400_000 + "</svg>"), "400 KB"),
], ids=["malformed", "no-title", "no-desc", "script", "script-in-comment", "foreign-object", "https", "http", "namespace-as-link", "oversize"])
def test_bad_svg_lists_path_and_reason(tmp_path, text, reason):
    folder = pair(tmp_path)
    (folder / "cells-dark.svg").write_text(text)
    result = run_check(tmp_path)
    assert result.returncode != 0
    assert "cells-dark.svg" in result.stdout
    assert reason in result.stdout


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_missing_variant_fails(tmp_path, mode):
    folder = tmp_path / "figures/cells"
    folder.mkdir(parents=True)
    (folder / f"cells-{mode}.svg").write_text(GOOD)
    result = run_check(tmp_path)
    assert result.returncode != 0
    assert "missing" in result.stdout
    assert ("dark" if mode == "light" else "light") in result.stdout
