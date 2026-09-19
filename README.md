# Theme Studio

Site-wide theming and white-labelling for the Frappe/ERPNext desk. An admin picks
colours, type and spacing in a form; every user on the site sees the result. Each
theme exports as a single `.theme.json` file you can upload to another instance.

Works on Frappe v15 and v16. Built to be installed on a live client site without
a maintenance window.

---

## What it does

| Area | Controls |
|---|---|
| Brand | App logo, favicon, login logo, login background, brand name, hide Frappe help menu and branding |
| Colours | Accent, page/card/control surfaces, borders, body/heading/muted text, navbar, sidebar, status colours, optional dark variant |
| Typography | System / Google Fonts / custom stylesheet URL, separate heading family, base size (everything else scales from it), weight, line height, letter spacing |
| Layout | Density, corner radius, button radius, card shadow, navbar height, sidebar width, page max width |
| Advanced | Apply to desk / website / login independently, raw CSS escape hatch for both desk and portal |

Plus: live preview in your own browser tab, three bundled presets, file export and
import, and a one-switch return to stock styling.

---

## How it works

Two mechanisms, deliberately redundant.

**1. A generated stylesheet.** On save, the theme compiles to CSS written to
`sites/<site>/public/files/theme_studio/desk.css`. `hooks.py` points
`app_include_css` at `/files/theme_studio/desk.css`. Because each site has its own
`public/files`, one static hook path resolves to a different file per site. This is
what paints the page *before* any JavaScript runs, so there is no flash of stock
colours on load.

**2. A boot payload.** `boot_session` attaches the same CSS to `frappe.boot`, and
`theme_studio.bundle.js` injects it as a `<style>` tag appended last in `<head>`.
Because it comes last, it wins on cascade order — so if a browser is holding a
cached copy of the file from mechanism 1, the injected copy silently corrects it.
Neither mechanism depends on the other working.

### Why it themes v16 and not just v15

Frappe v15 paints the desk from one family of CSS custom properties: `--bg-color`,
`--text-color`, `--primary`, `--gray-*`. v16 kept those for its older components
and added a second, semantic family borrowed from frappe-ui / Espresso:
`--surface-*`, `--ink-*`, `--outline-*`. The new v16 shell — collapsible sidebar,
command palette, settings dialog — paints from the Espresso family *alone*. A
v15-era theme therefore colours the content and leaves the shell stock, which is
the "half-themed" look you see in most ERPNext reskins.

Theme Studio emits **both families** from the same inputs. Emitting a token a
given version does not read is harmless — an unused CSS custom property does
nothing — so one theme file covers both versions with no branching.

The app also regenerates whole scales rather than setting a handful of variables.
Pick a page colour and a text colour and it interpolates `--gray-50` through
`--gray-900`, `--ink-gray-1` through `--ink-gray-9`, `--surface-gray-1..7` and
`--outline-gray-0..5` between them. That is the difference between a theme that
looks finished and one where half the desk stayed grey.

### Contrast is measured, not guessed

Leave sidebar text, navbar text or muted text blank and the app computes them by
WCAG relative luminance against the surface they sit on. Pick a near-black sidebar
and the labels go light; pick a pale one and they go dark. Muted text gets nudged
towards the ink colour until it clears 4:1, so "soft grey" stays soft right up to
the point it stops being readable. Saving a theme whose body text falls under
4.5:1 raises a warning but does not block you.

---

## Install

### Local bench

```bash
cd ~/frappe-bench
bench get-app theme_studio https://github.com/<you>/theme_studio.git
bench --site <site> install-app theme_studio
bench build --app theme_studio
bench --site <site> clear-cache
```

### Frappe Cloud

1. Push this repo to GitHub (private is fine — connect the repo to your Frappe
   Cloud account).
2. Bench group → **Apps** → **Add App** → **From GitHub** → pick the repo and
   branch.
3. **Deploy**. Frappe Cloud runs `bench build` and `bench migrate` for you.
4. Site → **Apps** → install `theme_studio` on the site.

Frappe Cloud needs `pyproject.toml` at the repo root and the package directory
named exactly `theme_studio` — both are already in place.

### After install

Nothing changes. The app installs **disabled**, which is why it is safe to put on
a live client site during business hours. Open **Theme Studio** in the desk
sidebar, create or import a theme, preview it, then press **Apply to Site**.

---

## Using it

**Build a theme.** Theme Studio → Themes → New, or Settings → *Start from a
preset* to fork one of the bundled ones. Save, then **Preview in this browser** —
preview is local to your tab, nothing is written to the site, so you can try a
theme on a live instance and nobody else sees it. **Apply to Site** makes it live
for everyone; open sessions pick it up over websocket without a hard refresh.

**Export.** On any theme: **Download theme file** → `<name>.theme.json`. The file
carries every design field plus the logo, favicon and login images base64-embedded
(up to 1 MB each), so it is self-contained.

**Import.** Settings → **Import theme file** → upload the `.theme.json`. Only
fields on the export whitelist are written, so a hand-edited or hostile file
cannot set `owner`, permissions, or anything the app has not reviewed. A name
clash gets a numeric suffix rather than silently overwriting.

That export/import pair is the reselling workflow: build the client's theme once
on your demo instance, download it, upload it on their production site.

---

## If a theme breaks the desk

Three ways out, in order of how little they need to work:

1. **`?no_theme=1`** — append it to any desk URL. Pure client-side, needs no
   server round trip.
2. **`theme_studio.disable()`** in the browser console. Persists in that browser
   until you run `theme_studio.enable()`.
3. **Settings → Turn theming off**, or `bench --site <site> set-value "Theme
   Studio Settings" "Theme Studio Settings" enabled 0`. Returns every user to
   stock styling without deleting anything.

Uninstalling (`bench --site <site> uninstall-app theme_studio`) removes the two
doctypes and the generated files. Nothing else on the site is touched.

---

## Safety properties worth knowing

- **No other doctype is modified.** No custom fields, no `doc_events`, no
  `override_doctype_class`, no overridden whitelisted methods. Installing changes
  how nothing else behaves, which is also why uninstalling is clean.
- **Nothing raises in the request path.** `boot_session` and
  `update_website_context` run on every login and every portal page. Both are
  wrapped; a compiler exception logs an Error Log entry and the site renders
  stock.
- **Input is validated, not trusted.** Colours must match a hex/rgb pattern or the
  save is rejected. Numeric fields are clamped to ranges that still render a
  usable desk (base font 10–22px, navbar 40–120px, and so on). Custom CSS has
  `<` stripped, script/expression/javascript-url patterns removed, and non-https
  `@import` blocked.
- **System Manager only**, checked explicitly in every whitelisted method rather
  than inherited from doctype permissions.
- **Degradation is per-value.** An unparseable colour is dropped from the output,
  not emitted — so a bad input means "that one thing stayed stock", never a broken
  stylesheet.

---

## Known limits

- **Custom JS is not supported and will not be.** A theme file that can execute
  JavaScript is a remote code execution vector the moment you accept theme files
  from anyone but yourself. Use a Client Script if you need behaviour.
- **The component rules are version-sensitive.** Roughly 90% of the theme is CSS
  custom properties, which are stable across versions. The remainder is a short
  block of selectors in `theme_builder.COMPONENT_RULES` for things Frappe does not
  expose as a variable — mainly the navbar and the sidebar, where v15 uses
  `.layout-side-section` / `.desk-sidebar` and v16 uses `.body-sidebar`. Both sets
  are present. If a future release renames them, that block is where to look; it
  is kept short on purpose.
- **Portal theming is intentionally light.** Frappe has its own Website Theme
  doctype for the portal, which compiles SCSS properly. Theme Studio's website
  output covers brand colours, fonts and the login page. For a heavily customised
  public site, use both.
- **Browser caching of the generated file.** `/files/theme_studio/desk.css` has no
  version query string, because the `app_include_css` hook value is static. A
  stale cached copy is corrected by the boot-injected stylesheet on the same page
  load, so you see the right theme either way — but a hard refresh is still the
  fastest way to confirm what a client is seeing.
- **Not yet tested against a live v16 instance.** The CSS compiler is unit-tested
  standalone; the Frappe integration is written against the documented hook API
  but has not been run on a real bench. Install on a staging site first.

---

## Repo layout

```
theme_studio/
├── pyproject.toml              # flit build config; Frappe Cloud reads this
├── README.md
├── FRAPPE_APP_DEVELOPMENT_GUIDE.md
└── theme_studio/
    ├── hooks.py                # framework integration points
    ├── boot.py                 # cache, generated files, boot payload
    ├── api.py                  # whitelisted endpoints (export/import/apply)
    ├── theme_builder.py        # the CSS compiler
    ├── colors.py               # colour maths: mixing, contrast, scales
    ├── install.py              # install/migrate/uninstall lifecycle
    ├── modules.txt             # declares the "Theme Studio" module
    ├── patches.txt
    ├── presets/                # bundled .theme.json starting points
    ├── public/js/theme_studio.bundle.js
    └── theme_studio/           # the module directory
        ├── doctype/
        │   ├── theme_studio_theme/
        │   └── theme_studio_settings/
        └── workspace/theme_studio/
```

## Licence

MIT. See `license.txt`.
