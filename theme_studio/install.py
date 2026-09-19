# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt

import frappe

from .boot import clear_theme_cache, remove_css_files, write_css_files


def after_install():
	"""Leave the site looking exactly as it did before installation.

	The app installs disabled. Nothing changes until someone picks a theme and
	presses Apply, which means installing on a live client site is a no-op you
	can do during business hours.
	"""
	try:
		settings = frappe.get_doc("Theme Studio Settings")
		settings.enabled = 0
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Theme Studio: after_install settings", message=frappe.get_traceback())

	_create_starter_theme()
	write_css_files()
	frappe.db.commit()


def _create_starter_theme():
	"""A single editable record so the first run is not an empty list view."""
	if frappe.db.exists("Theme Studio Theme", "Frappe Default"):
		return
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Theme Studio Theme",
				"theme_name": "Frappe Default",
				"description": "Stock Frappe colours. Duplicate this as a starting point.",
				"color_scheme": "Light",
				"primary_color": "#2490ef",
				"page_bg_color": "#f4f5f6",
				"card_bg_color": "#ffffff",
				"control_bg_color": "#f4f5f6",
				"border_color": "#e2e6e9",
				"text_color": "#383838",
				"heading_color": "#1f272e",
				"muted_text_color": "#7c7c7c",
				"navbar_bg_color": "#ffffff",
				"sidebar_bg_color": "#ffffff",
				"success_color": "#22a06b",
				"warning_color": "#e5a400",
				"danger_color": "#e24c4b",
				"font_source": "System",
				"base_font_size": 13,
				"heading_font_weight": "600",
				"line_height": 1.5,
				"density": "Default",
				"border_radius": 6,
				"navbar_height": 60,
				"sidebar_width": 240,
				"card_shadow": "Subtle",
				"apply_to_desk": 1,
				"apply_to_login": 1,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Theme Studio: starter theme", message=frappe.get_traceback())


def after_migrate():
	"""Regenerate the stylesheets after every `bench migrate`.

	Frappe Cloud runs migrate on deploy, so a schema change or a new version
	of the CSS compiler lands on the site without anyone re-saving a theme.
	"""
	try:
		clear_theme_cache()
	except Exception:
		frappe.log_error(title="Theme Studio: after_migrate", message=frappe.get_traceback())


def before_uninstall():
	"""Take the site back to stock before the doctypes disappear."""
	try:
		remove_css_files()
		frappe.clear_cache()
	except Exception:
		frappe.log_error(title="Theme Studio: before_uninstall", message=frappe.get_traceback())
