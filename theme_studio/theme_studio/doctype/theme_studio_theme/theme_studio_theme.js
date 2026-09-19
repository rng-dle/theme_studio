// Copyright (c) 2026, Nastiliq and contributors
// For license information, please see license.txt

frappe.ui.form.on("Theme Studio Theme", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.db.get_single_value("Theme Studio Settings", "active_theme").then((active) => {
			const is_active = active === frm.doc.name;

			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(
				is_active
					? __("This theme is live for every user on this site.")
					: __("Saved but not applied. Preview it, then press Apply to Site.")
			);

			if (!is_active) {
				frm.add_custom_button(__("Apply to Site"), () => apply_to_site(frm)).addClass(
					"btn-primary"
				);
			}

			frm.add_custom_button(__("Preview in this browser"), () => preview(frm), __("Theme"));
			frm.add_custom_button(__("Stop preview"), () => stop_preview(), __("Theme"));
			frm.add_custom_button(__("Download theme file"), () => download(frm), __("Theme"));
			frm.add_custom_button(__("Duplicate"), () => frm.copy_doc(), __("Theme"));
		});
	},
});

function apply_to_site(frm) {
	frappe.confirm(
		__("Apply <b>{0}</b> to every user on this site?", [frappe.utils.escape_html(frm.doc.name)]),
		() => {
			frappe.call({
				method: "theme_studio.api.apply_theme",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Applying theme..."),
				callback: () => {
					frappe.show_alert({ message: __("Theme applied"), indicator: "green" });
					setTimeout(() => window.location.reload(), 600);
				},
			});
		}
	);
}

function preview(frm) {
	// Preview is local to this browser tab only: nothing is written to the
	// site, so you can try a theme on a live instance without anyone noticing.
	frappe.call({
		method: "theme_studio.api.preview_css",
		args: { name: frm.doc.name },
		freeze: true,
		callback: (r) => {
			if (!r.message) return;
			let tag = document.getElementById("theme-studio-preview");
			if (!tag) {
				tag = document.createElement("style");
				tag.id = "theme-studio-preview";
				document.head.appendChild(tag);
			}
			document.head.appendChild(tag);
			tag.textContent = r.message;
			frappe.show_alert({
				message: __("Previewing in this tab only. Reload to discard."),
				indicator: "blue",
			});
		},
	});
}

function stop_preview() {
	const tag = document.getElementById("theme-studio-preview");
	if (tag) tag.remove();
	frappe.show_alert({ message: __("Preview stopped"), indicator: "gray" });
}

function download(frm) {
	const url =
		"/api/method/theme_studio.api.export_theme?name=" + encodeURIComponent(frm.doc.name);
	window.open(url, "_blank");
}
