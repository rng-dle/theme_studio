# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from theme_studio.boot import clear_theme_cache, get_payload


class ThemeStudioSettings(Document):
	def validate(self):
		if self.enabled and not self.active_theme:
			# Enabled with nothing selected would silently do nothing, which
			# reads as a broken app. Turn it back off instead.
			self.enabled = 0

	def on_update(self):
		try:
			clear_theme_cache()
			payload = get_payload()
			# Singles live in `tabSingles`, so set_value would look for a table
			# that does not exist. set_single_value is the right call here.
			frappe.db.set_single_value(self.doctype, "current_hash", payload.get("hash"))
			frappe.db.set_single_value(self.doctype, "last_applied_on", now_datetime())
			frappe.publish_realtime(
				"theme_studio:updated",
				{
					"css": payload.get("css"),
					"hash": payload.get("hash"),
					"enabled": payload.get("enabled"),
					"app_logo": payload.get("app_logo"),
					"favicon": payload.get("favicon"),
					"brand_name": payload.get("brand_name"),
				},
				after_commit=True,
			)
		except Exception:
			frappe.log_error(title="Theme Studio: settings update", message=frappe.get_traceback())
