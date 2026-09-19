# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from theme_studio.boot import clear_theme_cache, get_payload
from theme_studio.colors import contrast_ratio, is_color
from theme_studio.theme_builder import build_desk_css, sanitize_css

# Fields that must be a valid CSS colour if they are filled in at all.
COLOUR_FIELDS = [
	"primary_color",
	"page_bg_color",
	"card_bg_color",
	"control_bg_color",
	"border_color",
	"text_color",
	"heading_color",
	"muted_text_color",
	"navbar_bg_color",
	"navbar_text_color",
	"sidebar_bg_color",
	"sidebar_text_color",
	"sidebar_active_bg_color",
	"success_color",
	"warning_color",
	"danger_color",
	"login_background_color",
	"dark_primary_color",
	"dark_page_bg_color",
	"dark_card_bg_color",
	"dark_control_bg_color",
	"dark_border_color",
	"dark_text_color",
	"dark_navbar_bg_color",
	"dark_sidebar_bg_color",
]


class ThemeStudioTheme(Document):
	def validate(self):
		self.validate_colours()
		self.clamp_numbers()
		self.scrub_custom_css()
		self.warn_on_low_contrast()
		self.compile()

	def validate_colours(self):
		for field in COLOUR_FIELDS:
			value = self.get(field)
			if value and not is_color(value):
				label = self.meta.get_label(field)
				frappe.throw(_("{0} is not a valid colour.").format(label))

	def clamp_numbers(self):
		"""Keep every numeric input inside a range that still renders a usable
		desk. A 2px base font or a 900px navbar is a support ticket, not a
		design choice."""
		bounds = {
			"base_font_size": (10, 22, 13),
			"line_height": (1.0, 2.4, 1.5),
			"border_radius": (0, 32, 6),
			"button_border_radius": (0, 32, 0),
			"navbar_height": (40, 120, 60),
			"sidebar_width": (160, 420, 240),
			"page_max_width": (0, 2400, 0),
		}
		for field, (low, high, default) in bounds.items():
			value = self.get(field)
			if value in (None, ""):
				self.set(field, default)
				continue
			try:
				number = float(value)
			except (TypeError, ValueError):
				self.set(field, default)
				continue
			self.set(field, max(low, min(high, number)))

		if not self.button_border_radius:
			self.button_border_radius = self.border_radius

	def scrub_custom_css(self):
		for field in ("custom_css", "custom_website_css"):
			raw = self.get(field)
			if raw:
				cleaned = sanitize_css(raw)
				if cleaned != raw.strip():
					frappe.msgprint(
						_("Some unsafe rules were removed from {0}.").format(self.meta.get_label(field)),
						indicator="orange",
						alert=True,
					)
				self.set(field, cleaned)

	def warn_on_low_contrast(self):
		"""Advisory only. We do not block a save -- an admin may be mid-edit --
		but an unreadable desk should not be a surprise discovered by staff."""
		checks = [
			(self.text_color, self.card_bg_color, _("Body text on card background")),
			(self.text_color, self.page_bg_color, _("Body text on page background")),
		]
		for foreground, background, label in checks:
			if is_color(foreground) and is_color(background):
				ratio = contrast_ratio(foreground, background)
				if ratio < 4.5:
					frappe.msgprint(
						_("{0} has a contrast ratio of {1}:1, below the 4.5:1 readability floor.").format(
							label, round(ratio, 2)
						),
						indicator="orange",
						alert=True,
					)

	def compile(self):
		"""Store the compiled stylesheet on the record for inspection."""
		try:
			self.generated_css = build_desk_css(self)
		except Exception:
			self.generated_css = ""
			frappe.log_error(title="Theme Studio: compile", message=frappe.get_traceback())

	def on_update(self):
		self.refresh_site_theme()

	def on_trash(self):
		active = frappe.db.get_single_value("Theme Studio Settings", "active_theme")
		if active == self.name:
			frappe.db.set_single_value("Theme Studio Settings", "active_theme", None)
			frappe.db.set_single_value("Theme Studio Settings", "enabled", 0)
		self.refresh_site_theme()

	def refresh_site_theme(self):
		"""Only touch the live site if this theme is the active one."""
		try:
			active = frappe.db.get_single_value("Theme Studio Settings", "active_theme")
			if active != self.name:
				return
			clear_theme_cache()
			payload = get_payload()
			frappe.publish_realtime(
				"theme_studio:updated",
				{"css": payload.get("css"), "hash": payload.get("hash"),
				 "enabled": payload.get("enabled"), "app_logo": payload.get("app_logo"),
				 "favicon": payload.get("favicon"), "brand_name": payload.get("brand_name")},
				after_commit=True,
			)
		except Exception:
			frappe.log_error(title="Theme Studio: refresh", message=frappe.get_traceback())
