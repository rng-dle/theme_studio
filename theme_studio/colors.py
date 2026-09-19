# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt
"""Colour helpers.

Pure functions, no Frappe imports. Everything here is deliberately
defensive: bad input returns ``None`` rather than raising, because this
module runs inside ``boot_session`` and must never break a login.
"""

import re

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_RE = re.compile(
	r"^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*(?:0|1|0?\.\d+)\s*)?\)$"
)


def is_color(value) -> bool:
	"""True if ``value`` is a CSS colour we are willing to emit."""
	if not value or not isinstance(value, str):
		return False
	value = value.strip()
	return bool(HEX_RE.match(value) or RGB_RE.match(value))


def to_rgb(value):
	"""``"#2490ef"`` -> ``(36, 144, 239)``. Returns None if unparseable."""
	if not is_color(value):
		return None
	value = value.strip()

	if value.startswith("#"):
		h = value[1:]
		if len(h) in (3, 4):
			h = "".join(c * 2 for c in h[:3])
		h = h[:6]
		try:
			return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
		except ValueError:
			return None

	nums = re.findall(r"\d{1,3}", value)
	if len(nums) < 3:
		return None
	return tuple(min(255, int(n)) for n in nums[:3])


def to_hex(rgb) -> str:
	r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
	return f"#{r:02x}{g:02x}{b:02x}"


def mix(color_a, color_b, weight: float):
	"""Blend two colours. ``weight`` is how much of ``color_b`` to use (0..1)."""
	a, b = to_rgb(color_a), to_rgb(color_b)
	if not a or not b:
		return None
	weight = max(0.0, min(1.0, weight))
	return to_hex(tuple(a[i] + (b[i] - a[i]) * weight for i in range(3)))


def with_alpha(color, alpha: float) -> str | None:
	rgb = to_rgb(color)
	if not rgb:
		return None
	alpha = max(0.0, min(1.0, alpha))
	return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {round(alpha, 3)})"


def relative_luminance(color) -> float:
	"""WCAG 2.1 relative luminance. Returns 0.0 for unparseable input."""
	rgb = to_rgb(color)
	if not rgb:
		return 0.0

	def channel(c):
		c = c / 255.0
		return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

	r, g, b = (channel(c) for c in rgb)
	return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(color_a, color_b) -> float:
	la, lb = relative_luminance(color_a), relative_luminance(color_b)
	lighter, darker = max(la, lb), min(la, lb)
	return (lighter + 0.05) / (darker + 0.05)


def readable_ink(background, light="#ffffff", dark="#171717") -> str:
	"""Pick whichever of ``light``/``dark`` has more contrast on ``background``.

	This is what keeps sidebar labels and primary-button text legible no
	matter which colour the admin picks, instead of guessing from a
	light/dark flag.
	"""
	if not is_color(background):
		return dark
	return light if contrast_ratio(background, light) >= contrast_ratio(background, dark) else dark


def ensure_contrast(foreground, background, minimum=4.5, step=0.06, max_steps=14):
	"""Nudge ``foreground`` away from ``background`` until it clears ``minimum``.

	Used for muted text: the admin asks for a soft grey, and we keep it soft
	right up to the point where it stops being readable.
	"""
	if not is_color(foreground) or not is_color(background):
		return foreground
	if contrast_ratio(foreground, background) >= minimum:
		return foreground

	target = readable_ink(background)
	candidate = foreground
	for _ in range(max_steps):
		candidate = mix(candidate, target, step)
		if not candidate:
			return foreground
		if contrast_ratio(candidate, background) >= minimum:
			return candidate
	return candidate


def shade(color, amount: float):
	"""Darken (amount > 0) or lighten (amount < 0) a colour."""
	if amount >= 0:
		return mix(color, "#000000", amount)
	return mix(color, "#ffffff", -amount)


def build_scale(base, ink, stops):
	"""Interpolate a named scale from ``base`` (surface) towards ``ink`` (text).

	``stops`` is an ordered ``[(name, weight), ...]``. This is the reason a
	theme looks finished rather than half-applied: Frappe's desk paints from
	a full neutral ramp, so we regenerate the whole ramp from the two
	colours the admin actually chose.
	"""
	out = {}
	for name, weight in stops:
		value = mix(base, ink, weight)
		if value:
			out[name] = value
	return out


# Frappe's legacy (v15) neutral ramp, lightest to darkest.
GRAY_STOPS = [
	("50", 0.02),
	("100", 0.05),
	("200", 0.10),
	("300", 0.17),
	("400", 0.33),
	("500", 0.52),
	("600", 0.68),
	("700", 0.80),
	("800", 0.90),
	("900", 1.00),
]

# Espresso (v16) ink ramp: 1 is faintest text, 9 is strongest.
INK_GRAY_STOPS = [
	("1", 0.06),
	("2", 0.20),
	("3", 0.42),
	("4", 0.55),
	("5", 0.66),
	("6", 0.76),
	("7", 0.85),
	("8", 0.93),
	("9", 1.00),
]

# Espresso surface ramp: 1 is closest to the base surface, 7 is deepest.
SURFACE_GRAY_STOPS = [
	("1", 0.03),
	("2", 0.06),
	("3", 0.10),
	("4", 0.14),
	("5", 0.19),
	("6", 0.25),
	("7", 0.32),
]

# Espresso outline ramp for borders.
OUTLINE_GRAY_STOPS = [
	("0", 0.04),
	("1", 0.08),
	("2", 0.14),
	("3", 0.22),
	("4", 0.34),
	("5", 0.46),
]
