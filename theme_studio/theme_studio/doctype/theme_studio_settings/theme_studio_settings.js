// Copyright (c) 2026, Nastiliq and contributors
// For license information, please see license.txt

frappe.ui.form.on("Theme Studio Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Import theme file"), () => import_theme(frm));
		frm.add_custom_button(__("Start from a preset"), () => choose_preset(frm));
		frm.add_custom_button(__("Rebuild stylesheets"), () => rebuild(frm), __("Maintenance"));

		if (frm.doc.enabled) {
			frm.add_custom_button(__("Turn theming off"), () => deactivate(frm), __("Maintenance"));
		}

		frm.dashboard.set_headline(
			frm.doc.enabled && frm.doc.active_theme
				? __("Live: {0}", [frappe.utils.escape_html(frm.doc.active_theme)])
				: __("Theming is off. This site is showing stock Frappe styling.")
		);
	},
});

function import_theme(frm) {
	new frappe.ui.FileUploader({
		dialog_title: __("Import theme file"),
		restrictions: { allowed_file_types: [".json"] },
		on_success(file_doc) {
			frappe.call({
				method: "theme_studio.api.import_theme",
				args: { file_url: file_doc.file_url },
				freeze: true,
				freeze_message: __("Importing theme..."),
				callback(r) {
					if (!r.message) return;
					frappe.show_alert({
						message: __("Imported as {0}", [r.message.name]),
						indicator: "green",
					});
					frappe.set_route("Form", "Theme Studio Theme", r.message.name);
				},
			});
		},
	});
}

function choose_preset(frm) {
	frappe.call({
		method: "theme_studio.api.list_presets",
		callback(r) {
			const presets = r.message || [];
			if (!presets.length) {
				frappe.msgprint(__("No presets are bundled with this build."));
				return;
			}
			const d = new frappe.ui.Dialog({
				title: __("Start from a preset"),
				fields: [
					{
						fieldname: "preset",
						fieldtype: "Select",
						label: __("Preset"),
						reqd: 1,
						options: presets.map((p) => ({ label: p.label, value: p.file })),
					},
				],
				primary_action_label: __("Create theme"),
				primary_action(values) {
					d.hide();
					frappe.call({
						method: "theme_studio.api.install_preset",
						args: { file: values.preset },
						freeze: true,
						callback(res) {
							if (!res.message) return;
							frappe.set_route("Form", "Theme Studio Theme", res.message.name);
						},
					});
				},
			});
			d.show();
		},
	});
}

function rebuild(frm) {
	frappe.call({
		method: "theme_studio.api.rebuild",
		freeze: true,
		callback() {
			frappe.show_alert({ message: __("Stylesheets rebuilt"), indicator: "green" });
		},
	});
}

function deactivate(frm) {
	frappe.confirm(__("Return every user to stock Frappe styling?"), () => {
		frappe.call({
			method: "theme_studio.api.deactivate",
			freeze: true,
			callback() {
				window.location.reload();
			},
		});
	});
}
