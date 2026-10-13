import numpy as np
import pytest

from build import Geometry, Timing, cell_center, cell_points, oklab_lightness, ramp_color, row_delay, update_readme

GEOMETRY = Geometry(n=20)


def test_diagonal_cells_sit_on_the_bottom_row():
    ys = [cell_center(k, k, GEOMETRY)[1] for k in range(GEOMETRY.n)]
    assert ys == pytest.approx([GEOMETRY.base - GEOMETRY.half_height] * GEOMETRY.n)


def test_apex_cell_is_centred_horizontally():
    assert cell_center(GEOMETRY.n - 1, 0, GEOMETRY)[0] == pytest.approx(GEOMETRY.width / 2)


def test_next_query_row_shares_an_edge_with_the_cell_below_it():
    top, right, _, _ = cell_points(7, 3, GEOMETRY, inset=0)
    _, _, bottom, left = cell_points(8, 3, GEOMETRY, inset=0)
    assert {top, right} == {left, bottom}


def test_ramp_endpoints_are_the_stop_colours_in_both_modes():
    assert (ramp_color(0, "light"), ramp_color(1, "light")) == ("#cde2fb", "#0d366b")
    assert (ramp_color(0, "dark"), ramp_color(1, "dark")) == ("#0d366b", "#cde2fb")


def test_ramp_gets_darker_with_weight_in_light_mode():
    lightness = [oklab_lightness(ramp_color(t, "light")) for t in np.linspace(0, 1, 41)]
    assert all(later < earlier for earlier, later in zip(lightness, lightness[1:]))


def test_row_delay_grows_along_the_sweep_and_across_scenes():
    timing = Timing()
    assert row_delay(0, 1, timing) > row_delay(0, 0, timing)
    assert row_delay(1, 0, timing) == pytest.approx(timing.scene)


def test_update_readme_replaces_only_the_marked_block():
    text = "intro\n<!-- header:start -->\nold\n<!-- header:end -->\noutro\n"
    assert update_readme(text, "new") == "intro\n<!-- header:start -->\nnew\n<!-- header:end -->\noutro\n"
