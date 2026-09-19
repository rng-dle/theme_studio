# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt
"""Runtime plumbing: cache, generated files, and the desk boot payload.

Nothing in this module is allowed to raise. It runs on every login and on
every portal page render, so a broken theme has to degrade into "the site
looks stock", never "the site is down". Every public function here is
wrapped.
"""

import hashlib
import os

import frappe

from .theme_builder import build_desk_css, build_website_css

DESK_CSS_PATH = ("theme_studio", "desk.css")
WEBSITE_CSS_PATH = ("theme_studio", "website.css")

CACHE_KEY = "theme_studio:payload"


def _cache():
	"""frappe.cache is a function in v15 and an attribute in later builds."""
	c = getattr(frappe, "cache", None)
	return c() if callable(c) else c


def _log(title):
	try:
		frappe.log_error(title=f"Theme Studio: {title}", message=frappe.get_traceback())
	except Exception:
		pass


# ---------------------------------------------------------------------------
# active theme
# ---------------------------------------------------------------------------


def get_active_theme():
	"""Return the active theme document, or None when the app is idle."""
	try:
		if not frappe.db.exists("DocType", "Theme Studio Settings"):
			return None
		settings = frappe.get_cached_doc("Theme Studio Settings")
		if not settings.get("enabled") or not settings.get("active_theme"):
			return None
		if not frappe.db.exists("Theme Studio Theme", settings.active_theme):
			return None
		return frappe.get_cached_doc("Theme Studio Theme", settings.active_theme)
	except Exception:
		_log("get_active_theme")
		return None


def build_payload() -> dict:
	"""Compile everything the browser needs, in one cacheable dict."""
	theme = get_active_theme()
	if not theme:
		return {"enabled": 0}

	desk_css = build_desk_css(theme) if theme.get("apply_to_desk") else ""
	website_css = build_website_css(theme)

	payload = {
		"enabled": 1,
		"theme": theme.name,
		"brand_name": theme.get("brand_name") or "",
		"app_logo": theme.get("app_logo") or "",
		"favicon": theme.get("favicon") or "",
		"login_logo": theme.get("login_logo") or "",
		"color_scheme": theme.get("color_scheme") or "Light",
		"hide_help_menu": 1 if theme.get("hide_help_menu") else 0,
		"css": desk_css,
		"hash": hashlib.md5((desk_css + website_css).encode("utf-8")).hexdigest()[:10],
	}
	payload["website_css"] = website_css
	return payload


def get_payload() -> dict:
	try:
		cache = _cache()
		if cache:
			cached = cache.get_value(CACHE_KEY)
			if cached:
				return cached
		payload = build_payload()
		if cache:
			cache.set_value(CACHE_KEY, payload)
		return payload
	except Exception:
		_log("get_payload")
		return {"enabled": 0}


def clear_theme_cache(write_files: bool = True):
	"""Called whenever a theme or the settings change."""
	try:
		cache = _cache()
		if cache:
			cache.delete_value(CACHE_KEY)

		# Targeted, not frappe.clear_cache(). A blanket flush would rebuild
		# every doctype's metadata on a live ERPNext site just because someone
		# nudged a colour.
		frappe.clear_document_cache("Theme Studio Settings", "Theme Studio Settings")
		active = frappe.db.get_single_value("Theme Studio Settings", "active_theme")
		if active:
			frappe.clear_document_cache("Theme Studio Theme", active)

		if write_files:
			write_css_files()
	except Exception:
		_log("clear_theme_cache")


# ---------------------------------------------------------------------------
# generated files
# ---------------------------------------------------------------------------


def _site_file(parts):
	return frappe.get_site_path("public", "files", *parts)


def write_css_files():
	"""Write the generated stylesheets into the site's public files.

	These are what ``app_include_css`` / ``web_include_css`` point at, which
	is how the theme renders before any JavaScript has run -- no flash of the
	stock colours. The boot-injected copy is applied afterwards and wins on
	cascade order, so a browser holding a stale copy of this file still ends
	up correct.
	"""
	payload = build_payload()
	desk_css = payload.get("css") or "/* Theme Studio: no active theme */\n"
	website_css = payload.get("website_css") or "/* Theme Studio: no active theme */\n"

	for parts, content in ((DESK_CSS_PATH, desk_css), (WEBSITE_CSS_PATH, website_css)):
		try:
			path = _site_file(parts)
			os.makedirs(os.path.dirname(path), exist_ok=True)
			with open(path, "w", encoding="utf-8") as f:
				f.write(content)
		except Exception:
			# A read-only or missing files directory is survivable: the boot
			# payload still carries the CSS.
			_log(f"write_css_files:{'/'.join(parts)}")


def remove_css_files():
	for parts in (DESK_CSS_PATH, WEBSITE_CSS_PATH):
		try:
			path = _site_file(parts)
			if os.path.exists(path):
				os.remove(path)
		except Exception:
			_log("remove_css_files")


# ---------------------------------------------------------------------------
# hooks
# ---------------------------------------------------------------------------


def boot_session(bootinfo):
	"""``boot_session`` hook: attach the theme to frappe.boot."""
	try:
		payload = get_payload()
		bootinfo.theme_studio = payload
		if payload.get("enabled") and payload.get("app_logo"):
			# Frappe reads this for the navbar / splash logo.
			bootinfo.app_logo_url = payload["app_logo"]
	except Exception:
		_log("boot_session")
		try:
			bootinfo.theme_studio = {"enabled": 0}
		except Exception:
			pass


def update_website_context(context):
	"""``update_website_context`` hook: brand the portal and login page."""
	try:
		payload = get_payload()
		if not payload.get("enabled"):
			return context
		if payload.get("favicon"):
			context.favicon = payload["favicon"]
		if payload.get("brand_name"):
			context.app_name = payload["brand_name"]
		if payload.get("login_logo") or payload.get("app_logo"):
			context.app_logo_url = payload.get("login_logo") or payload.get("app_logo")
		context.theme_studio = {
			"brand_name": payload.get("brand_name"),
			"login_logo": payload.get("login_logo") or payload.get("app_logo"),
		}
	except Exception:
		_log("update_website_context")
	return context
