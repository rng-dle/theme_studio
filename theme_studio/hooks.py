# Copyright (c) 2026, Nastiliq and contributors
# For license information, please see license.txt

app_name = "theme_studio"
app_title = "Theme Studio"
app_publisher = "Nastiliq"
app_description = "Site-wide theming and white-labelling for the Frappe/ERPNext desk"
app_email = "hello@example.com"
app_license = "mit"

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
# The bundle is the injector: it reads frappe.boot.theme_studio and applies the
# theme. It is built by `bench build --app theme_studio`.
app_include_js = "theme_studio.bundle.js"

# Generated per-site stylesheets. These are written into the site's own public
# files directory, which is why a single static path works for every site on a
# bench. They exist so the theme is painted by the browser before any JS runs.
# If the file is missing the request 404s harmlessly and the boot-injected copy
# still applies.
app_include_css = "/files/theme_studio/desk.css"
web_include_css = "/files/theme_studio/website.css"

# ---------------------------------------------------------------------------
# Desk presence
# ---------------------------------------------------------------------------
# v15+ apps screen / v16 desktop screen. Without this the app has no icon and
# is only reachable by URL.
add_to_apps_screen = [
	{
		"name": "theme_studio",
		"logo": "/assets/theme_studio/images/theme_studio.svg",
		"title": "Theme Studio",
		"route": "/app/theme-studio",
		"has_permission": "theme_studio.api.has_app_permission",
	}
]

# ---------------------------------------------------------------------------
# Session and website
# ---------------------------------------------------------------------------
boot_session = "theme_studio.boot.boot_session"
update_website_context = "theme_studio.boot.update_website_context"

# ---------------------------------------------------------------------------
# Install lifecycle
# ---------------------------------------------------------------------------
after_install = "theme_studio.install.after_install"
after_migrate = "theme_studio.install.after_migrate"
before_uninstall = "theme_studio.install.before_uninstall"

# ---------------------------------------------------------------------------
# Deliberately not used
# ---------------------------------------------------------------------------
# override_whitelisted_methods, override_doctype_class, doc_events:
#   this app touches no other doctype, which is what keeps it safe to install
#   on a live ERPNext site and safe to uninstall again.
