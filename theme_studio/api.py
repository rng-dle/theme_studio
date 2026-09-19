# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt
"""Whitelisted endpoints.

Every method here requires System Manager. Themes control what every user in
the site sees, so the permission check is explicit rather than inherited.
"""

import base64
import json
import os
from datetime import datetime

import frappe
from frappe import _

from .boot import clear_theme_cache, get_payload
from .theme_builder import build_desk_css

FILE_FORMAT_VERSION = 1

# Fields carried in an exported theme file. Import writes only these, so a
# hand-edited or hostile file cannot set `owner`, `name`, permissions, or any
# field added later that we have not reviewed.
EXPORTABLE_FIELDS = [
	"description",
	"brand_name",
	"hide_help_menu",
	"hide_frappe_branding",
	"footer_text",
	"color_scheme",
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
	"enable_dark_variant",
	"dark_primary_color",
	"dark_page_bg_color",
	"dark_card_bg_color",
	"dark_control_bg_color",
	"dark_border_color",
	"dark_text_color",
	"dark_navbar_bg_color",
	"dark_sidebar_bg_color",
	"font_source",
	"font_family",
	"google_font_weights",
	"custom_font_url",
	"heading_font_family",
	"base_font_size",
	"heading_font_weight",
	"letter_spacing",
	"line_height",
	"density",
	"border_radius",
	"button_border_radius",
	"navbar_height",
	"sidebar_width",
	"card_shadow",
	"page_max_width",
	"apply_to_desk",
	"apply_to_website",
	"apply_to_login",
	"custom_css",
	"custom_website_css",
	"login_background_color",
]

# Image fields embedded in the export so a theme file is self-contained.
ASSET_FIELDS = ["app_logo", "favicon", "login_logo", "login_background_image"]

MAX_EMBEDDED_ASSET_BYTES = 1024 * 1024  # 1 MB per image
MAX_IMPORT_BYTES = 8 * 1024 * 1024


def _check_permission():
	if frappe.session.user == "Administrator":
		return
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can manage themes."), frappe.PermissionError)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


def _read_attachment(file_url):
	"""Return base64 content for an attached file, or None."""
	if not file_url or not isinstance(file_url, str) or not file_url.startswith("/"):
		return None
	try:
		name = frappe.db.get_value("File", {"file_url": file_url}, "name")
		if not name:
			return None
		file_doc = frappe.get_doc("File", name)
		content = file_doc.get_content()
		if isinstance(content, str):
			content = content.encode("utf-8")
		if len(content) > MAX_EMBEDDED_ASSET_BYTES:
			return None
		return {
			"file_name": file_doc.file_name,
			"content": base64.b64encode(content).decode("ascii"),
		}
	except Exception:
		frappe.log_error(title="Theme Studio: export asset", message=frappe.get_traceback())
		return None


def build_export_payload(name: str) -> dict:
	theme = frappe.get_doc("Theme Studio Theme", name)

	payload = {
		"file_format": "theme-studio-theme",
		"file_format_version": FILE_FORMAT_VERSION,
		"exported_on": datetime.utcnow().isoformat() + "Z",
		"exported_from": frappe.local.site,
		"theme_name": theme.name,
		"theme": {},
		"assets": {},
	}

	for field in EXPORTABLE_FIELDS:
		value = theme.get(field)
		if value not in (None, ""):
			payload["theme"][field] = value

	for field in ASSET_FIELDS:
		asset = _read_attachment(theme.get(field))
		if asset:
			payload["assets"][field] = asset

	return payload


@frappe.whitelist()
def export_theme(name: str):
	"""Stream one theme as a ``.theme.json`` download."""
	_check_permission()
	payload = build_export_payload(name)

	safe_name = frappe.scrub(name) or "theme"
	frappe.response["filename"] = f"{safe_name}.theme.json"
	frappe.response["filecontent"] = json.dumps(payload, indent=2, default=str)
	frappe.response["type"] = "download"


@frappe.whitelist()
def export_theme_json(name: str) -> str:
	"""Same payload, returned inline (for copy-paste or API clients)."""
	_check_permission()
	return json.dumps(build_export_payload(name), indent=2, default=str)


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


def _restore_asset(field, asset):
	try:
		raw = base64.b64decode(asset["content"])
		if len(raw) > MAX_EMBEDDED_ASSET_BYTES:
			return None
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": asset.get("file_name") or f"{field}.png",
				"is_private": 0,
				"content": raw,
			}
		)
		file_doc.flags.ignore_permissions = True
		file_doc.insert(ignore_permissions=True)
		return file_doc.file_url
	except Exception:
		frappe.log_error(title="Theme Studio: import asset", message=frappe.get_traceback())
		return None


def _unique_theme_name(preferred: str) -> str:
	base = (preferred or "Imported Theme").strip()[:120]
	candidate, counter = base, 2
	while frappe.db.exists("Theme Studio Theme", candidate):
		candidate = f"{base} {counter}"
		counter += 1
	return candidate


@frappe.whitelist()
def import_theme(file_url: str = None, json_text: str = None, overwrite: int = 0, theme_name: str = None):
	"""Create a theme from an exported ``.theme.json`` file.

	Accepts either an uploaded file URL or raw JSON text. Unknown keys are
	ignored: only fields in ``EXPORTABLE_FIELDS`` are written.
	"""
	_check_permission()

	raw = None
	if json_text:
		raw = json_text
	elif file_url:
		file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
		if not file_name:
			frappe.throw(_("Uploaded file not found."))
		content = frappe.get_doc("File", file_name).get_content()
		raw = content.decode("utf-8") if isinstance(content, bytes) else content
	else:
		frappe.throw(_("Provide a theme file or JSON text."))

	if len(raw) > MAX_IMPORT_BYTES:
		frappe.throw(_("Theme file is too large."))

	try:
		payload = json.loads(raw)
	except ValueError:
		frappe.throw(_("That file is not valid JSON."))

	if not isinstance(payload, dict) or payload.get("file_format") != "theme-studio-theme":
		frappe.throw(_("That file was not exported by Theme Studio."))

	if int(payload.get("file_format_version", 1)) > FILE_FORMAT_VERSION:
		frappe.throw(
			_("This theme file was made by a newer version of Theme Studio. Update the app first.")
		)

	incoming = payload.get("theme") or {}
	if not isinstance(incoming, dict):
		frappe.throw(_("Theme file is malformed."))

	target_name = theme_name or payload.get("theme_name") or "Imported Theme"

	if frappe.db.exists("Theme Studio Theme", target_name) and int(overwrite or 0):
		doc = frappe.get_doc("Theme Studio Theme", target_name)
	else:
		doc = frappe.new_doc("Theme Studio Theme")
		doc.theme_name = _unique_theme_name(target_name)

	for field in EXPORTABLE_FIELDS:
		if field in incoming:
			doc.set(field, incoming[field])

	for field, asset in (payload.get("assets") or {}).items():
		if field in ASSET_FIELDS and isinstance(asset, dict):
			url = _restore_asset(field, asset)
			if url:
				doc.set(field, url)

	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"name": doc.name}


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------


def _preset_dir():
	# Inside the package, not at the repo root, so presets ship with the app
	# whether it is pip-installed editable (bench) or built as a wheel.
	return os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")


@frappe.whitelist()
def list_presets():
	_check_permission()
	out = []
	try:
		for entry in sorted(os.listdir(_preset_dir())):
			if entry.endswith(".theme.json"):
				out.append({"file": entry, "label": entry.replace(".theme.json", "").replace("-", " ").title()})
	except Exception:
		pass
	return out


@frappe.whitelist()
def install_preset(file: str):
	"""Copy a bundled preset into a new editable theme record."""
	_check_permission()
	if "/" in file or "\\" in file or not file.endswith(".theme.json"):
		frappe.throw(_("Invalid preset."))

	path = os.path.join(_preset_dir(), file)
	if not os.path.exists(path):
		frappe.throw(_("Preset not found."))

	with open(path, encoding="utf-8") as f:
		return import_theme(json_text=f.read())


# ---------------------------------------------------------------------------
# apply / preview
# ---------------------------------------------------------------------------


@frappe.whitelist()
def apply_theme(name: str):
	"""Make ``name`` the site-wide active theme."""
	_check_permission()
	if not frappe.db.exists("Theme Studio Theme", name):
		frappe.throw(_("Theme not found."))

	settings = frappe.get_doc("Theme Studio Settings")
	settings.enabled = 1
	settings.active_theme = name
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	frappe.db.commit()

	return {"active_theme": name}


@frappe.whitelist()
def deactivate():
	"""Return the site to stock Frappe styling without deleting anything."""
	_check_permission()
	settings = frappe.get_doc("Theme Studio Settings")
	settings.enabled = 0
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	return {"enabled": 0}


@frappe.whitelist()
def preview_css(name: str) -> str:
	"""CSS for a theme that is not active, for in-browser preview only."""
	_check_permission()
	theme = frappe.get_doc("Theme Studio Theme", name)
	return build_desk_css(theme)


@frappe.whitelist()
def rebuild():
	"""Force-regenerate the cached payload and the generated files."""
	_check_permission()
	clear_theme_cache()
	return get_payload().get("hash")


def has_app_permission():
	"""Used by the ``add_to_apps_screen`` hook."""
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()
