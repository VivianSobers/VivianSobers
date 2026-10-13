from pathlib import Path

import pytest

from figkit.text import Face, Outliner, run_start

ROOT = Path(__file__).resolve().parents[1]
MONA = ROOT / "figkit" / "fonts" / "MonaSansVF[wdth,opsz,wght].ttf"


@pytest.fixture(scope="module")
def mona():
    return Face(MONA, {"wdth": 125, "wght": 600})


def test_advance_applies_the_fonts_kerning_at_the_chosen_instance(mona):
    # Measured with HarfBuzz: "AV" is 1626 units kerned, 1730 unkerned, at wdth 125 wght 600.
    assert mona.advance("AV", size=1000) == pytest.approx(1626)


def test_advance_scales_linearly_with_size(mona):
    assert mona.advance("Vivian", size=44) == pytest.approx(2 * mona.advance("Vivian", size=22))


def test_run_start_follows_the_anchor():
    assert run_start(x=500, width=200, anchor="start") == 500
    assert run_start(x=500, width=200, anchor="middle") == 400
    assert run_start(x=500, width=200, anchor="end") == 300


def test_repeated_glyphs_share_one_definition(mona):
    outliner = Outliner()
    outliner.run(mona, "VV", x=0, y=0, size=20)
    assert outliner.defs().count("<path ") == 1


def test_space_emits_no_glyph(mona):
    outliner = Outliner()
    assert outliner.run(mona, "A V", x=0, y=0, size=20).count("<use ") == 2


def test_same_glyph_from_two_instances_gets_two_definitions(mona):
    outliner = Outliner()
    outliner.run(mona, "V", x=0, y=0, size=20)
    outliner.run(Face(MONA, {"wdth": 100, "wght": 400}), "V", x=0, y=0, size=20)
    assert outliner.defs().count("<path ") == 2



def test_shared_power_run_keeps_the_existing_raised_digit_output(mona):
    from figkit.text import power_run
    out = Outliner()
    width = mona.advance("10", 13) + mona.advance("−5", 9.1)
    start = 200 - width
    expected = out.run(mona, "10", start, 100, 13)
    expected += out.run(mona, "−5", start + mona.advance("10", 13), 94.8, 9.1)
    assert power_run(out, mona, ("10", "−5"), 200, 100, 13, "end") == expected
    assert power_run(out, mona, ("12", ""), 200, 100, 13) == out.run(mona, "12", 200, 100, 13)
