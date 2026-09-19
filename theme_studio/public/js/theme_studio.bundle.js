/**
 * Theme Studio desk injector.
 *
 * Applies the active theme from `frappe.boot.theme_studio`, which the
 * `boot_session` hook puts there. A generated stylesheet is also served from
 * /files/theme_studio/desk.css via `app_include_css`; that one paints the page
 * before any JS runs, and this one is appended afterwards so it wins on
 * cascade order whenever the browser is holding a stale copy of the file.
 *
 * Escape hatches, in case a theme ever renders the desk unusable:
 *   - add ?no_theme=1 to any desk URL
 *   - run theme_studio.disable() in the browser console (persists per browser)
 * Neither needs a server round trip, so both work when you are locked out of
 * a form you cannot see.
 */

(function () {
	"use strict";

	var STYLE_ID = "theme-studio-desk";
	var STORAGE_KEY = "theme_studio_disabled";
	var attempts = 0;

	function suppressed() {
		try {
			if (window.location.search.indexOf("no_theme=1") !== -1) return true;
			return window.localStorage.getItem(STORAGE_KEY) === "1";
		} catch (e) {
			return false;
		}
	}

	function payload() {
		try {
			return (window.frappe && frappe.boot && frappe.boot.theme_studio) || null;
		} catch (e) {
			return null;
		}
	}

	function injectStyle(css) {
		var tag = document.getElementById(STYLE_ID);
		if (!tag) {
			tag = document.createElement("style");
			tag.id = STYLE_ID;
			tag.setAttribute("type", "text/css");
			(document.head || document.documentElement).appendChild(tag);
		} else if (tag.parentNode) {
			// Re-append so it stays last in the head and keeps priority over
			// any stylesheet Frappe adds after boot.
			tag.parentNode.appendChild(tag);
		}
		tag.textContent = css || "";
	}

	function removeStyle() {
		var tag = document.getElementById(STYLE_ID);
		if (tag && tag.parentNode) tag.parentNode.removeChild(tag);
	}

	function setFavicon(url) {
		if (!url) return;
		try {
			var links = document.querySelectorAll("link[rel*='icon']");
			for (var i = 0; i < links.length; i++) {
				links[i].parentNode.removeChild(links[i]);
			}
			var link = document.createElement("link");
			link.rel = "shortcut icon";
			link.href = url;
			document.head.appendChild(link);
		} catch (e) {
			/* a favicon is never worth an exception */
		}
	}

	function applyBranding(data) {
		if (!data) return;
		setFavicon(data.favicon);

		if (data.app_logo) {
			try {
				frappe.boot.app_logo_url = data.app_logo;
				var logos = document.querySelectorAll(".navbar-brand img, .app-logo img, img.app-logo");
				for (var i = 0; i < logos.length; i++) {
					logos[i].setAttribute("src", data.app_logo);
				}
			} catch (e) {
				/* noop */
			}
		}

		if (data.brand_name) {
			try {
				var suffix = " - " + data.brand_name;
				if (document.title.indexOf(suffix) === -1) {
					document.title = document.title.split(" - ")[0] + suffix;
				}
			} catch (e) {
				/* noop */
			}
		}
	}

	function apply() {
		if (suppressed()) {
			removeStyle();
			return true;
		}

		var data = payload();
		if (!data) return false; // boot not ready yet

		if (!data.enabled) {
			removeStyle();
			return true;
		}

		injectStyle(data.css);
		applyBranding(data);
		return true;
	}

	function retry() {
		if (apply()) return;
		attempts += 1;
		if (attempts < 40) setTimeout(retry, 50);
	}

	// Try immediately; frappe.boot is usually already on the page.
	retry();

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", apply);
	}

	// Re-apply after Frappe has drawn the shell, so the navbar logo and any
	// late-mounted components pick the theme up.
	try {
		if (window.$) {
			$(document).on("app_ready startup", function () {
				setTimeout(apply, 0);
			});
		}
	} catch (e) {
		/* noop */
	}

	function refreshFromServer() {
		try {
			frappe.call({
				method: "theme_studio.api.rebuild",
				callback: function () {
					frappe.call({
						method: "frappe.client.get_value",
						args: { doctype: "Theme Studio Settings", fieldname: "active_theme" },
						callback: function () {
							window.location.reload();
						},
					});
				},
			});
		} catch (e) {
			window.location.reload();
		}
	}

	// Live update: when an admin applies a theme, every open desk session
	// picks it up without anyone being told to hard-refresh.
	try {
		if (window.frappe && frappe.realtime && frappe.realtime.on) {
			frappe.realtime.on("theme_studio:updated", function (data) {
				if (suppressed()) return;
				if (data && data.css) {
					injectStyle(data.css);
					applyBranding(data);
				} else {
					refreshFromServer();
				}
			});
		}
	} catch (e) {
		/* noop */
	}

	window.theme_studio = {
		apply: apply,
		disable: function () {
			try {
				window.localStorage.setItem(STORAGE_KEY, "1");
			} catch (e) {}
			removeStyle();
			return "Theme Studio disabled in this browser. Run theme_studio.enable() to undo.";
		},
		enable: function () {
			try {
				window.localStorage.removeItem(STORAGE_KEY);
			} catch (e) {}
			apply();
			return "Theme Studio re-enabled in this browser.";
		},
		payload: payload,
	};
})();
