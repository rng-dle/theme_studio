# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt
"""Compile a Theme Studio Theme document into CSS.

Design notes
------------
1. We drive Frappe's own design tokens rather than fighting them with
   ``!important`` on component selectors. Frappe v15 paints the desk from one
   family of CSS custom properties (``--bg-color``, ``--text-color``,
   ``--primary`` ...). Frappe v16 kept those for its older components and
   added a second, semantic family borrowed from frappe-ui / Espresso
   (``--surface-*``, ``--ink-*``, ``--outline-*``). The new v16 desk shell --
   collapsible sidebar, command palette, settings dialog -- paints from the
   Espresso family alone. So we emit BOTH families from the same inputs, and
   the app themes v15 and v16 without branching.

2. Emitting a token that a given version does not read is harmless: an unused
   CSS custom property does nothing. That is what makes the both-families
   approach safe across upgrades.

3. Every value is validated before it reaches the stylesheet. A malformed
   colour is dropped, not emitted, so a bad input degrades to "that one thing
   stayed stock" rather than a broken page.
"""

import re

from . import colors as C

# Anything that could break out of a <style> block or pull in an executable
# resource. Admins are trusted (System Manager only), this is defence in depth.
DANGEROUS_CSS = re.compile(
	r"(</\s*style|<\s*script|javascript\s*:|expression\s*\(|behavior\s*:|-moz-binding)",
	re.IGNORECASE,
)

SAFE_FONT_NAME = re.compile(r"^[A-Za-z0-9 ,'\"_-]{1,120}$")

FONT_SCALE = [
	("xs", 0.85),
	("sm", 0.92),
	("base", 1.00),
	("md", 1.08),
	("lg", 1.23),
	("xl", 1.38),
	("2xl", 1.69),
	("3xl", 2.15),
	("4xl", 2.77),
]

PADDING_SCALE = [
	("xs", 5),
	("sm", 8),
	("md", 12),
	("lg", 15),
	("xl", 20),
	("2xl", 30),
]

DENSITY_FACTOR = {"Compact": 0.75, "Default": 1.0, "Spacious": 1.30}

SHADOW_PRESETS = {
	"None": ("none", "none", "none", "none"),
	"Subtle": (
		"0 0 0 1px rgba(0,0,0,0.04)",
		"0 1px 2px rgba(0,0,0,0.05)",
		"0 2px 6px rgba(0,0,0,0.06)",
		"0 8px 20px rgba(0,0,0,0.08)",
	),
	"Medium": (
		"0 0 0 1px rgba(0,0,0,0.05)",
		"0 1px 3px rgba(0,0,0,0.10)",
		"0 4px 10px rgba(0,0,0,0.10)",
		"0 12px 28px rgba(0,0,0,0.14)",
	),
	"Strong": (
		"0 0 0 1px rgba(0,0,0,0.07)",
		"0 2px 5px rgba(0,0,0,0.16)",
		"0 6px 16px rgba(0,0,0,0.18)",
		"0 18px 40px rgba(0,0,0,0.24)",
	),
}


# ---------------------------------------------------------------------------
# input handling
# ---------------------------------------------------------------------------


def _get(theme, field, default=None):
	"""Read a field from either a Frappe Document or a plain dict."""
	if theme is None:
		return default
	if isinstance(theme, dict):
		value = theme.get(field)
	else:
		value = getattr(theme, field, None)
	return default if value in (None, "") else value


def _color(theme, field, fallback=None):
	value = _get(theme, field)
	return value if C.is_color(value) else fallback


def _int(theme, field, fallback, low, high):
	try:
		value = int(float(_get(theme, field, fallback)))
	except (TypeError, ValueError):
		return fallback
	return max(low, min(high, value))


def _float(theme, field, fallback, low, high):
	try:
		value = float(_get(theme, field, fallback))
	except (TypeError, ValueError):
		return fallback
	return max(low, min(high, value))


def sanitize_css(raw) -> str:
	"""Strip anything that could escape the stylesheet context.

	``<`` has no valid use in CSS, so removing it outright closes
	``</style>`` and ``<script>`` with no residue left behind. ``>`` is kept
	because it is the child combinator.
	"""
	if not raw or not isinstance(raw, str):
		return ""
	cleaned = DANGEROUS_CSS.sub("/* removed */", raw)
	cleaned = cleaned.replace("<", "")
	# Only allow @import over https, so a theme file cannot pull in http or
	# data-url payloads.
	cleaned = re.sub(
		r"@import\s+(?!url\(\s*['\"]?https://)[^;]*;", "/* blocked @import */", cleaned, flags=re.I
	)
	return cleaned.strip()


def sanitize_font_stack(raw, fallback='-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'):
	if not raw or not isinstance(raw, str) or not SAFE_FONT_NAME.match(raw.strip()):
		return fallback
	name = raw.strip()
	if "," in name:
		return name
	quoted = f'"{name}"' if " " in name else name
	return f"{quoted}, {fallback}"


# ---------------------------------------------------------------------------
# palette
# ---------------------------------------------------------------------------


def build_palette(theme, dark: bool = False) -> dict:
	"""Return the full ``{css-variable: value}`` map for one colour mode."""
	prefix = "dark_" if dark else ""

	if dark:
		surface = _color(theme, "dark_page_bg_color", "#141414")
		card = _color(theme, "dark_card_bg_color", "#1c1c1c")
		control = _color(theme, "dark_control_bg_color", card)
		ink = _color(theme, "dark_text_color", "#e8e8e8")
		border = _color(theme, "dark_border_color", C.mix(surface, ink, 0.18))
		primary = _color(theme, "dark_primary_color") or _color(theme, "primary_color", "#2490ef")
		navbar = _color(theme, "dark_navbar_bg_color", card)
		sidebar = _color(theme, "dark_sidebar_bg_color", surface)
		sidebar_ink = _color(theme, "sidebar_text_color")
		navbar_ink = _color(theme, "navbar_text_color")
	else:
		surface = _color(theme, "page_bg_color", "#f4f5f6")
		card = _color(theme, "card_bg_color", "#ffffff")
		control = _color(theme, "control_bg_color", surface)
		ink = _color(theme, "text_color", "#383838")
		border = _color(theme, "border_color", C.mix(surface, ink, 0.16))
		primary = _color(theme, "primary_color", "#2490ef")
		navbar = _color(theme, "navbar_bg_color", card)
		sidebar = _color(theme, "sidebar_bg_color", card)
		sidebar_ink = _color(theme, "sidebar_text_color")
		navbar_ink = _color(theme, "navbar_text_color")

	heading = _color(theme, f"{prefix}heading_color") or _color(theme, "heading_color") or ink
	muted = _color(theme, "muted_text_color") or C.mix(card, ink, 0.55)
	muted = C.ensure_contrast(muted, card, minimum=4.0)

	# Text that sits on coloured surfaces is measured, never assumed.
	sidebar_ink = sidebar_ink or C.readable_ink(sidebar, dark="#171717")
	navbar_ink = navbar_ink or C.readable_ink(navbar, dark="#171717")
	on_primary = C.readable_ink(primary)

	success = _color(theme, "success_color", "#22a06b")
	warning = _color(theme, "warning_color", "#e5a400")
	danger = _color(theme, "danger_color", "#e24c4b")

	v = {}

	# -- legacy family (v15, and v16's older components) --------------------
	v["--bg-color"] = surface
	v["--fg-color"] = card
	v["--card-bg"] = card
	v["--subtle-fg"] = C.mix(card, ink, 0.05)
	v["--subtle-accent"] = C.mix(card, primary, 0.08)
	v["--control-bg"] = control
	v["--control-bg-on-gray"] = C.mix(control, ink, 0.05)
	v["--disabled-control-bg"] = C.mix(control, ink, 0.07)
	v["--awesomebar-focus-bg"] = card
	v["--modal-bg"] = card
	v["--navbar-bg"] = navbar
	v["--sidebar-bg"] = sidebar
	v["--border-color"] = border
	v["--dark-border-color"] = C.mix(border, ink, 0.25)
	v["--text-color"] = ink
	v["--heading-color"] = heading
	v["--text-light"] = C.mix(card, ink, 0.70)
	v["--text-muted"] = muted
	v["--text-muted-color"] = muted
	v["--text-on-dark-bg"] = "#ffffff"
	v["--primary"] = primary
	v["--primary-color"] = primary
	v["--text-on-primary"] = on_primary
	v["--btn-primary"] = primary
	v["--btn-primary-bg"] = primary
	v["--btn-primary-color"] = on_primary
	v["--icon-fill"] = "transparent"
	v["--icon-stroke"] = C.mix(card, ink, 0.72)

	# Neutral ramp. Frappe derives dozens of desk colours from these, so
	# regenerating the whole ramp is what stops a theme looking half-applied.
	for name, value in C.build_scale(surface, ink, C.GRAY_STOPS).items():
		v[f"--gray-{name}"] = value

	# Accent ramp, so hovers/active states track the chosen accent.
	for step, amount in (("50", -0.92), ("100", -0.82), ("200", -0.62), ("300", -0.40),
	                     ("400", -0.18), ("500", 0.0), ("600", 0.14), ("700", 0.28),
	                     ("800", 0.42), ("900", 0.56)):
		shaded = C.shade(primary, amount)
		if shaded:
			v[f"--blue-{step}"] = shaded

	v["--blue-avatar-bg"] = C.mix(card, primary, 0.18)
	v["--blue-avatar-color"] = C.shade(primary, 0.25)

	for name, base in (("green", success), ("red", danger), ("orange", warning), ("yellow", warning)):
		for step, amount in (("100", -0.82), ("300", -0.42), ("500", 0.0), ("600", 0.15), ("700", 0.3)):
			shaded = C.shade(base, amount)
			if shaded:
				v[f"--{name}-{step}"] = shaded

	v["--alert-bg-success"] = C.mix(card, success, 0.16)
	v["--alert-bg-danger"] = C.mix(card, danger, 0.16)
	v["--alert-bg-warning"] = C.mix(card, warning, 0.16)
	v["--alert-bg-info"] = C.mix(card, primary, 0.16)

	# -- Espresso family (v16 shell) ---------------------------------------
	v["--surface-white"] = card
	v["--surface-base"] = surface
	v["--surface-modal"] = card
	v["--surface-cards"] = card
	v["--surface-menu-bar"] = navbar
	v["--surface-selected"] = C.mix(card, primary, 0.12)
	v["--surface-amber-1"] = C.mix(card, warning, 0.12)
	v["--surface-red-1"] = C.mix(card, danger, 0.12)
	v["--surface-green-1"] = C.mix(card, success, 0.12)
	v["--surface-blue-1"] = C.mix(card, primary, 0.12)
	v["--surface-blue-2"] = C.mix(card, primary, 0.22)

	for name, value in C.build_scale(card, ink, C.SURFACE_GRAY_STOPS).items():
		v[f"--surface-gray-{name}"] = value

	for name, value in C.build_scale(card, ink, C.INK_GRAY_STOPS).items():
		v[f"--ink-gray-{name}"] = value

	v["--ink-white"] = card
	v["--ink-black"] = ink
	v["--ink-blue-1"] = C.shade(primary, -0.30)
	v["--ink-blue-2"] = C.shade(primary, -0.10)
	v["--ink-blue-3"] = primary
	v["--ink-blue-4"] = C.shade(primary, 0.18)
	v["--ink-red-3"] = danger
	v["--ink-green-3"] = success
	v["--ink-amber-3"] = warning

	for name, value in C.build_scale(card, border, C.OUTLINE_GRAY_STOPS).items():
		v[f"--outline-gray-{name}"] = value
	v["--outline-white"] = card

	v["--bg-gray-1"] = C.mix(card, ink, 0.04)
	v["--bg-gray-2"] = C.mix(card, ink, 0.08)

	# -- surfaces we expose to our own component rules ----------------------
	v["--ts-sidebar-bg"] = sidebar
	v["--ts-sidebar-ink"] = sidebar_ink
	v["--ts-sidebar-muted"] = C.ensure_contrast(C.mix(sidebar, sidebar_ink, 0.65), sidebar, 4.0)
	v["--ts-sidebar-hover"] = C.mix(sidebar, sidebar_ink, 0.08)
	v["--ts-sidebar-active"] = _color(theme, "sidebar_active_bg_color") or C.mix(sidebar, primary, 0.18)
	v["--ts-navbar-bg"] = navbar
	v["--ts-navbar-ink"] = navbar_ink
	v["--ts-navbar-border"] = C.mix(navbar, ink, 0.12)

	return {k: val for k, val in v.items() if val}


# ---------------------------------------------------------------------------
# non-colour tokens
# ---------------------------------------------------------------------------


def build_metrics(theme) -> dict:
	v = {}

	base_size = _int(theme, "base_font_size", 13, 10, 22)
	for name, ratio in FONT_SCALE:
		size = round(base_size * ratio)
		v[f"--text-{name}"] = f"{size}px"
		v[f"--font-size-{name}"] = f"{size}px"
	v["--text-base"] = f"{base_size}px"
	v["--font-size-base"] = f"{base_size}px"

	body_font = sanitize_font_stack(_get(theme, "font_family"))
	heading_font = _get(theme, "heading_font_family")
	v["--font-stack"] = body_font
	v["--font-family"] = body_font
	v["--heading-font-stack"] = sanitize_font_stack(heading_font, body_font) if heading_font else body_font

	line_height = _float(theme, "line_height", 1.5, 1.0, 2.4)
	v["--line-height-base"] = str(line_height)
	v["--body-line-height"] = str(line_height)

	spacing = _get(theme, "letter_spacing")
	if spacing and re.match(r"^-?\d{1,2}(\.\d{1,3})?(px|em|rem)?$", str(spacing).strip()):
		spacing = str(spacing).strip()
		v["--letter-spacing"] = spacing if spacing[-1].isalpha() else f"{spacing}px"

	weight = _get(theme, "heading_font_weight", "600")
	if str(weight) in {"400", "500", "600", "700", "800"}:
		v["--text-bold"] = str(weight)
		v["--heading-font-weight"] = str(weight)

	factor = DENSITY_FACTOR.get(_get(theme, "density", "Default"), 1.0)
	for name, px in PADDING_SCALE:
		value = f"{max(2, round(px * factor))}px"
		v[f"--padding-{name}"] = value
		v[f"--margin-{name}"] = value

	radius = _int(theme, "border_radius", 6, 0, 32)
	v["--border-radius"] = f"{radius}px"
	v["--border-radius-sm"] = f"{max(0, radius - 2)}px"
	v["--border-radius-md"] = f"{radius}px"
	v["--border-radius-lg"] = f"{radius + 4}px"
	v["--border-radius-xl"] = f"{radius + 8}px"
	v["--border-radius-full"] = "999px"
	v["--radius-sm"] = f"{max(0, radius - 2)}px"
	v["--radius-base"] = f"{radius}px"
	v["--radius-lg"] = f"{radius + 4}px"
	v["--radius-xl"] = f"{radius + 8}px"

	btn_radius = _int(theme, "button_border_radius", radius, 0, 32)
	v["--ts-button-radius"] = f"{btn_radius}px"

	navbar_height = _int(theme, "navbar_height", 60, 40, 120)
	v["--navbar-height"] = f"{navbar_height}px"
	v["--ts-navbar-height"] = f"{navbar_height}px"

	v["--ts-sidebar-width"] = f"{_int(theme, 'sidebar_width', 240, 160, 420)}px"

	sm, base, md, lg = SHADOW_PRESETS.get(_get(theme, "card_shadow", "Subtle"), SHADOW_PRESETS["Subtle"])
	v["--shadow-sm"] = sm
	v["--shadow-base"] = base
	v["--shadow-md"] = md
	v["--shadow-lg"] = lg
	v["--card-shadow"] = base

	max_width = _int(theme, "page_max_width", 0, 0, 2400)
	if max_width:
		v["--ts-page-max-width"] = f"{max_width}px"

	return {k: val for k, val in v.items() if val}


def _font_import(theme) -> str:
	source = _get(theme, "font_source", "System")
	if source == "Google Fonts":
		family = _get(theme, "font_family")
		if not family or not SAFE_FONT_NAME.match(str(family)):
			return ""
		weights = str(_get(theme, "google_font_weights", "400;500;600;700"))
		if not re.match(r"^\d{3}(;\d{3})*$", weights):
			weights = "400;500;600;700"
		family_param = str(family).strip().replace(" ", "+")
		return (
			f"@import url('https://fonts.googleapis.com/css2?family="
			f"{family_param}:wght@{weights}&display=swap');"
		)
	if source == "Custom URL":
		url = str(_get(theme, "custom_font_url", "")).strip()
		if url.startswith("https://") and '"' not in url and "'" not in url and ")" not in url:
			return f"@import url('{url}');"
	return ""


# ---------------------------------------------------------------------------
# component rules
# ---------------------------------------------------------------------------

# Selectors Frappe does not expose as a variable. Kept short on purpose --
# every extra selector here is one more thing that can break on upgrade.
# The version-specific sidebar classes are grouped so they are easy to amend:
#   v15: .layout-side-section, .desk-sidebar
#   v16: .body-sidebar, .sidebar-container
COMPONENT_RULES = """
body, .layout-main, .page-body {
	font-family: var(--font-stack);
	font-size: var(--text-base);
	line-height: var(--line-height-base);
	letter-spacing: var(--letter-spacing, normal);
}

h1, h2, h3, h4, h5, h6, .page-title, .title-text, .ellipsis.title-text {
	font-family: var(--heading-font-stack);
	font-weight: var(--heading-font-weight, 600);
	color: var(--heading-color);
}

.btn, .btn-default, .btn-secondary, .btn-primary {
	border-radius: var(--ts-button-radius);
}

.navbar, .navbar-expand, header .navbar {
	background-color: var(--ts-navbar-bg) !important;
	color: var(--ts-navbar-ink);
	min-height: var(--ts-navbar-height);
	border-bottom: 1px solid var(--ts-navbar-border);
}
.navbar .nav-link, .navbar .navbar-nav > li > a, .navbar .dropdown-toggle {
	color: var(--ts-navbar-ink) !important;
}
.navbar .navbar-brand img, .app-logo, .navbar-brand .app-logo {
	max-height: calc(var(--ts-navbar-height) - 24px);
	width: auto;
}

/* Sidebar: v16 shell first, then the v15 classes. */
.body-sidebar, .sidebar-container, .desk-sidebar, .layout-side-section > .sidebar {
	background-color: var(--ts-sidebar-bg) !important;
	color: var(--ts-sidebar-ink);
	width: var(--ts-sidebar-width);
}
.body-sidebar a, .body-sidebar .sidebar-item-label, .body-sidebar span,
.desk-sidebar .desk-sidebar-item .sidebar-item-label,
.layout-side-section .sidebar-label, .layout-side-section a {
	color: var(--ts-sidebar-ink) !important;
}
.body-sidebar .text-ink-gray-5, .body-sidebar .text-muted,
.desk-sidebar .text-muted, .layout-side-section .text-muted {
	color: var(--ts-sidebar-muted) !important;
}
.body-sidebar .sidebar-item:hover, .desk-sidebar .desk-sidebar-item:hover,
.standard-sidebar-item:hover {
	background-color: var(--ts-sidebar-hover) !important;
}
.body-sidebar .sidebar-item.selected, .desk-sidebar .desk-sidebar-item.selected,
.standard-sidebar-item.selected {
	background-color: var(--ts-sidebar-active) !important;
}

.widget, .form-section, .frappe-card, .list-row-container, .page-head {
	border-radius: var(--border-radius);
}
.widget, .frappe-card {
	box-shadow: var(--card-shadow);
}
"""

PAGE_WIDTH_RULE = """
.container.page-body, .page-body .container, .layout-main-section-wrapper {
	max-width: var(--ts-page-max-width);
}
"""


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------


def _block(selector: str, variables: dict) -> str:
	if not variables:
		return ""
	body = "\n".join(f"\t{k}: {val};" for k, val in sorted(variables.items()))
	return f"{selector} {{\n{body}\n}}\n"


def build_desk_css(theme) -> str:
	"""Full desk stylesheet for one theme document."""
	if theme is None:
		return ""

	parts = []
	font_import = _font_import(theme)
	if font_import:
		parts.append(font_import)  # must stay first: @import is invalid later

	parts.append("/* Theme Studio - generated file, do not edit by hand */")

	light = build_palette(theme, dark=False)
	light.update(build_metrics(theme))

	scheme = _get(theme, "color_scheme", "Light")
	if scheme == "Dark":
		# The admin wants dark as the single look: apply the dark palette to
		# the default scope so it renders even before the theme switcher runs.
		dark = build_palette(theme, dark=True)
		dark.update(build_metrics(theme))
		parts.append(_block(':root, [data-theme="light"], [data-theme="dark"]', dark))
	else:
		parts.append(_block(':root, [data-theme="light"]', light))
		if _get(theme, "enable_dark_variant"):
			dark = build_palette(theme, dark=True)
			dark.update(build_metrics(theme))
			parts.append(_block('[data-theme="dark"]', dark))

	parts.append(COMPONENT_RULES)

	if _int(theme, "page_max_width", 0, 0, 2400):
		parts.append(PAGE_WIDTH_RULE)

	if _get(theme, "hide_help_menu"):
		parts.append(
			".navbar .dropdown-help, .navbar .dropdown-help + .dropdown-menu { display: none !important; }\n"
		)

	if _get(theme, "hide_frappe_branding"):
		parts.append(
			".app-footer, .footer-powered, .navbar .frappe-versions, "
			".about-link, [data-label='Frappe%20Framework'] { display: none !important; }\n"
		)

	custom = sanitize_css(_get(theme, "custom_css"))
	if custom:
		parts.append("/* custom css */\n" + custom + "\n")

	return "\n".join(p for p in parts if p).strip() + "\n"


def build_website_css(theme) -> str:
	"""Portal / login stylesheet. Deliberately lighter than the desk one."""
	# The login page still gets branded even when the portal is left stock,
	# because that is the page a client's staff see first.
	if theme is None or not (_get(theme, "apply_to_website") or _get(theme, "apply_to_login")):
		return ""

	parts = []
	font_import = _font_import(theme)
	if font_import:
		parts.append(font_import)

	parts.append("/* Theme Studio - website - generated file, do not edit by hand */")

	if _get(theme, "apply_to_website"):
		palette = build_palette(theme, dark=(_get(theme, "color_scheme") == "Dark"))
		palette.update(build_metrics(theme))
		parts.append(_block(":root", palette))
		parts.append(
			"body { font-family: var(--font-stack); background-color: var(--bg-color); "
			"color: var(--text-color); }\n"
			".navbar { background-color: var(--ts-navbar-bg) !important; }\n"
			".btn-primary { background-color: var(--primary); border-color: var(--primary); "
			"color: var(--text-on-primary); border-radius: var(--ts-button-radius); }\n"
		)

	if _get(theme, "apply_to_login"):
		bg = _color(theme, "login_background_color")
		image = _get(theme, "login_background_image")
		login_rules = []
		if bg:
			login_rules.append(f"background-color: {bg};")
		if image and isinstance(image, str) and image.startswith("/"):
			safe = image.replace('"', "").replace(")", "")
			login_rules.append(f'background-image: url("{safe}");')
			login_rules.append("background-size: cover;")
			login_rules.append("background-position: center;")
		if login_rules:
			parts.append(
				'body[data-path="login"], .page-card-container {\n\t'
				+ "\n\t".join(login_rules)
				+ "\n}\n"
			)
		card_radius = _int(theme, "border_radius", 6, 0, 32)
		parts.append(f".page-card {{ border-radius: {card_radius + 4}px; }}\n")

	custom = sanitize_css(_get(theme, "custom_website_css"))
	if custom:
		parts.append("/* custom website css */\n" + custom + "\n")

	return "\n".join(p for p in parts if p).strip() + "\n"
