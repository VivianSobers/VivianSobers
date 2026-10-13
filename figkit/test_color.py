from math import dist

import numpy as np
import pytest

from figkit.color import BLUE, EMBER, oklab_lightness, ramp_color, to_oklab


def test_ramp_endpoints_are_the_stop_colours_in_both_modes():
    assert (ramp_color(0, "light"), ramp_color(1, "light")) == ("#cde2fb", "#0d366b")
    assert (ramp_color(0, "dark"), ramp_color(1, "dark")) == ("#0d366b", "#cde2fb")


def test_ramp_gets_darker_with_weight_in_light_mode():
    lightness = [oklab_lightness(ramp_color(t, "light")) for t in np.linspace(0, 1, 41)]
    assert all(later < earlier for earlier, later in zip(lightness, lightness[1:]))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_accents_are_separated_in_oklab(mode):
    assert dist(to_oklab(BLUE[mode]), to_oklab(EMBER[mode])) > 0.2
