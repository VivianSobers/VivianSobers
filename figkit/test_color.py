from math import atan2, degrees, dist, hypot
import re

import numpy as np
import pytest

from figkit.color import BLUE, EMBER, oklab_lightness, ramp_color, to_oklab
from figkit import color


CATEGORICAL = {
    "blue": {"light": "#2a78d6", "dark": "#3987e5"},
    "orange": {"light": "#eb6834", "dark": "#d95926"},
    "aqua": {"light": "#1baf7a", "dark": "#199e70"},
    "yellow": {"light": "#eda100", "dark": "#c98500"},
    "magenta": {"light": "#e87ba4", "dark": "#d55181"},
    "green": {"light": "#008300", "dark": "#008300"},
    "violet": {"light": "#6250d6", "dark": "#9085e9"},
    "red": {"light": "#e34948", "dark": "#e66767"},
}
ANCHORS = [value for modes in CATEGORICAL.values() for value in modes.values()]


def test_categorical_palette_values():
    assert color.CATEGORICAL == CATEGORICAL


def test_status_palette_values():
    assert color.STATUS == {
        "good": "#0ca30c", "warning": "#fab219",
        "serious": "#ec835a", "critical": "#d03b3b",
    }


def test_legacy_palette_values_stay_unchanged():
    assert BLUE == {"light": "#256abf", "dark": "#3987e5"}
    assert EMBER == {"light": "#d9622b", "dark": "#e0702f"}
    assert color.RAMP == (
        "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
        "#256abf", "#184f95", "#0d366b",
    )


@pytest.mark.parametrize("anchor", ANCHORS)
def test_hue_ramp_has_ramp_shape_and_light_to_dark_endpoints(anchor):
    stops = color.hue_ramp(anchor)
    assert isinstance(stops, tuple)
    assert len(stops) == len(color.RAMP)
    assert all(re.fullmatch(r"#[0-9a-f]{6}", stop) for stop in stops)
    assert oklab_lightness(stops[0]) == pytest.approx(0.95, abs=0.002)
    assert oklab_lightness(stops[-1]) == pytest.approx(0.30, abs=0.002)


@pytest.mark.parametrize("anchor", ANCHORS)
def test_hue_ramp_lightness_strictly_decreases_in_even_steps(anchor):
    lightness = [oklab_lightness(stop) for stop in color.hue_ramp(anchor)]
    assert all(later < earlier for earlier, later in zip(lightness, lightness[1:]))
    assert lightness == pytest.approx(np.linspace(0.95, 0.30, 7), abs=0.002)


@pytest.mark.parametrize("anchor", ANCHORS)
def test_hue_ramp_keeps_anchor_hue_by_reducing_chroma(anchor):
    _, a, b = to_oklab(anchor)
    hue = degrees(atan2(b, a))
    for stop in color.hue_ramp(anchor):
        _, step_a, step_b = to_oklab(stop)
        difference = (degrees(atan2(step_b, step_a)) - hue + 180) % 360 - 180
        assert abs(difference) <= 8
        assert 0 < hypot(step_a, step_b) <= hypot(a, b) + 0.002


@pytest.mark.parametrize("steps", [2, 4, 11])
def test_hue_ramp_accepts_a_custom_stop_count(steps):
    stops = color.hue_ramp("#6250d6", steps=steps)
    assert len(stops) == steps
    assert [oklab_lightness(stop) for stop in stops] == pytest.approx(
        np.linspace(0.95, 0.30, steps), abs=0.002,
    )


@pytest.mark.parametrize("steps", [-1, 0, 1])
def test_hue_ramp_needs_two_stops_for_both_endpoints(steps):
    with pytest.raises(ValueError, match="at least two"):
        color.hue_ramp("#6250d6", steps=steps)


def test_ramp_endpoints_are_the_stop_colours_in_both_modes():
    assert (ramp_color(0, "light"), ramp_color(1, "light")) == ("#cde2fb", "#0d366b")
    assert (ramp_color(0, "dark"), ramp_color(1, "dark")) == ("#0d366b", "#cde2fb")


def test_ramp_gets_darker_with_weight_in_light_mode():
    lightness = [oklab_lightness(ramp_color(t, "light")) for t in np.linspace(0, 1, 41)]
    assert all(later < earlier for earlier, later in zip(lightness, lightness[1:]))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_accents_are_separated_in_oklab(mode):
    assert dist(to_oklab(BLUE[mode]), to_oklab(EMBER[mode])) > 0.2


@pytest.mark.parametrize("channels, expected", [
    ((0, 0.0031308, 1), "#000aff"),
    ((0.25, 0.5, 0.75), "#89bce1"),
    ((-1, 2, 0), "#00ff00"),
])
def test_linear_rgb_encodes_both_transfer_branches_and_clamps(channels, expected):
    from figkit.color import linear_to_srgb_hex
    assert linear_to_srgb_hex(channels) == expected
