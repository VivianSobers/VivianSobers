import math

# The sequential blue that marks Qwen3-0.6B in the qk-attribution figures, light to dark.
RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
INK = {"light": "#1f2328", "dark": "#f0f6fc"}
MUTED = {"light": "#59636e", "dark": "#9198a1"}
FAINT = {"light": "#d1d9e0", "dark": "#3d444d"}
BLUE = {"light": "#256abf", "dark": "#3987e5"}
EMBER = {"light": "#d9622b", "dark": "#e0702f"}
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
STATUS = {
    "good": "#0ca30c", "warning": "#fab219",
    "serious": "#ec835a", "critical": "#d03b3b",
}


def _to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _from_linear(channel: float) -> float:
    channel = min(max(channel, 0.0), 1.0)
    return 12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055


def linear_to_srgb_hex(channels) -> str:
    return "#" + "".join(f"{round(_from_linear(channel) * 255):02x}" for channel in channels)


def to_oklab(hex_color: str) -> tuple[float, float, float]:
    r, g, b = (_to_linear(int(hex_color[k : k + 2], 16) / 255) for k in (1, 3, 5))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def _oklab_to_linear(lightness: float, a: float, b: float) -> tuple[float, float, float]:
    l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def from_oklab(lightness: float, a: float, b: float) -> str:
    return linear_to_srgb_hex(_oklab_to_linear(lightness, a, b))


def hue_ramp(hex_color: str, steps: int = 7) -> tuple[str, ...]:
    if steps < 2:
        raise ValueError("a ramp needs at least two stops")
    _, a, b = to_oklab(hex_color)
    stops = []
    for k in range(steps):
        lightness = 0.95 - 0.65 * k / (steps - 1)
        scale = 1.0
        if not all(0 <= c <= 1 for c in _oklab_to_linear(lightness, a, b)):
            lo, hi = 0.0, 1.0
            for _ in range(24):
                scale = (lo + hi) / 2
                if all(0 <= c <= 1 for c in _oklab_to_linear(lightness, a * scale, b * scale)):
                    lo = scale
                else:
                    hi = scale
            scale = lo
        stops.append(from_oklab(lightness, a * scale, b * scale))
    return tuple(stops)


def oklab_lightness(hex_color: str) -> float:
    return to_oklab(hex_color)[0]


def ramp_color(t: float, mode: str) -> str:
    """t = 0 is no attention and recedes toward the page; t = 1 is full attention."""
    stops = RAMP if mode == "light" else RAMP[::-1]
    position = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    k = min(int(position), len(stops) - 2)
    fraction = position - k
    if fraction in (0.0, 1.0):
        return stops[k + int(fraction)]
    lo, hi = to_oklab(stops[k]), to_oklab(stops[k + 1])
    return from_oklab(*(p + (q - p) * fraction for p, q in zip(lo, hi)))
