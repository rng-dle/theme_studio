# Building Custom Apps on Frappe Framework

A working reference for building, shipping and maintaining custom apps on Frappe
v15/v16 — written for someone packaging ERPNext for resale, where every
customisation has to survive an upstream upgrade and be reinstallable on the next
client's site.

Theme Studio (in this repo) is used as the worked example throughout, so every
pattern below has a real file you can open next to it.

---

## Contents

1. [The mental model](#1-the-mental-model)
2. [Creating an app](#2-creating-an-app)
3. [Anatomy of an app](#3-anatomy-of-an-app)
4. [hooks.py](#4-hookspy)
5. [DocTypes](#5-doctypes)
6. [Controllers](#6-controllers)
7. [Client scripts](#7-client-scripts)
8. [Server-side API](#8-server-side-api)
9. [Extending other apps](#9-extending-other-apps)
10. [Assets and the build system](#10-assets-and-the-build-system)
11. [Desk presence: workspaces and the apps screen](#11-desk-presence-workspaces-and-the-apps-screen)
12. [Fixtures, patches and migrations](#12-fixtures-patches-and-migrations)
13. [Background jobs and the scheduler](#13-background-jobs-and-the-scheduler)
14. [Permissions](#14-permissions)
15. [Testing](#15-testing)
16. [Deployment](#16-deployment)
17. [Staying upgrade-safe as a reseller](#17-staying-upgrade-safe-as-a-reseller)
18. [Pitfalls](#18-pitfalls)
19. [Command reference](#19-command-reference)

---

## 1. The mental model

Three things that are easy to conflate:

- **Bench** — a directory tree and a CLI. Holds the Python virtualenv, the Node
  toolchain, the app source code in `apps/`, and the sites in `sites/`. One bench
  serves many sites.
- **App** — a Python package plus metadata. Lives once in `apps/<app_name>`, is
  shared by every site on the bench. Code, not data.
- **Site** — a MariaDB database plus a `sites/<site>/` directory holding its
  config and its uploaded files. Data, not code.

Installing an app on a site means: run its `before_install`/`after_install` hooks,
create the database tables for its DocTypes, sync its fixtures, and add its name
to that site's installed-apps list. Same code, different rows, per site.

```
frappe-bench/
├── apps/
│   ├── frappe/
│   ├── erpnext/
│   └── theme_studio/          ← your app, one copy
├── sites/
│   ├── apps.txt               ← apps available on this bench
│   ├── client-a.local/
│   │   ├── site_config.json
│   │   └── public/files/      ← per-site uploads
│   └── client-b.local/
└── env/
```

The practical consequence, and the one that bites people: **anything in `apps/`
is shared**. A hook value is the same for every site on the bench. If you need
per-site behaviour, it has to come from the database or from a per-site path. (See
how `app_include_css` in Theme Studio points at `/files/...`, which resolves to a
different file for each site, rather than at `/assets/...`, which would not.)

---

## 2. Creating an app

```bash
cd ~/frappe-bench
bench new-app theme_studio
```

It prompts for title, publisher, description, licence, and generates the skeleton.
App names must be valid Python module names: lowercase, underscores, no hyphens.
The repo folder may use hyphens, but then `bench get-app` will not resolve it
automatically — keep both the same and save yourself the trouble.

Install it on a site:

```bash
bench --site dev.local install-app theme_studio
```

For development you want developer mode on, or DocType edits made in the UI will
be written to the database instead of to files:

```bash
bench --site dev.local set-config developer_mode 1
bench --site dev.local clear-cache
```

**Developer mode belongs on your machine only.** Never on production, never on
Frappe Cloud. Its whole purpose is to make schema edits write files into `apps/`,
which is exactly what you do not want happening on a client's live site.

---

## 3. Anatomy of an app

```
theme_studio/                       ← repo root
├── pyproject.toml                  ← package metadata (flit). Frappe Cloud reads this.
├── README.md
├── license.txt
└── theme_studio/                   ← the Python package
    ├── __init__.py                 ← must define __version__
    ├── hooks.py                    ← every framework integration point
    ├── modules.txt                 ← one line per module the app declares
    ├── patches.txt                 ← data migration scripts, in order
    ├── install.py                  ← install/uninstall lifecycle (by convention)
    ├── api.py                      ← whitelisted endpoints (by convention)
    ├── public/                     ← static assets → symlinked to /assets/theme_studio/
    │   ├── js/
    │   ├── css/
    │   └── images/
    ├── templates/                  ← Jinja templates for portal pages
    ├── www/                        ← file-based portal routes
    └── theme_studio/               ← a module directory (name from modules.txt)
        ├── doctype/
        │   └── theme_studio_theme/
        │       ├── theme_studio_theme.json   ← schema
        │       ├── theme_studio_theme.py     ← server controller
        │       ├── theme_studio_theme.js     ← client controller
        │       └── test_theme_studio_theme.py
        ├── workspace/
        ├── report/
        └── page/
```

The doubled directory name is not a mistake. `theme_studio/theme_studio/` is the
**module**, a namespace inside the app. Most apps have one module with the same
name as the app; ERPNext has many (Accounts, Stock, Selling...). Every DocType
belongs to exactly one module, declared by its `module` field, and the module must
be listed in `modules.txt` or `bench migrate` will refuse to import it.

Two files people forget:

- `__init__.py` must set `__version__`. Some tooling reads it.
- Every directory in the Python path needs an `__init__.py`, including
  `doctype/` and each individual doctype folder. A missing one produces a
  "module not found" during migrate that reads like a framework bug.

---

## 4. hooks.py

`hooks.py` is a flat Python module of module-level names. Frappe collects them
across all installed apps with `frappe.get_hooks("name")`, which always returns a
list (or a dict of lists). Multiple apps can hook the same event; they all run.

Inspect what is actually registered:

```bash
bench --site dev.local console
>>> frappe.get_hooks("app_include_js")
```

### App identity

```python
app_name = "theme_studio"          # must match the package directory
app_title = "Theme Studio"
app_publisher = "Nastiliq"
app_description = "..."
app_email = "hello@example.com"
app_license = "mit"
```

### Assets

```python
app_include_js = "theme_studio.bundle.js"   # desk, every page
app_include_css = "/files/theme_studio/desk.css"
web_include_js = "theme_studio_web.bundle.js"   # portal, every page
web_include_css = "/files/theme_studio/website.css"

page_js = {"background_jobs": "public/js/custom_background_jobs.js"}
doctype_js = {"Sales Invoice": "public/js/sales_invoice.js"}
doctype_list_js = {"Sales Invoice": "public/js/sales_invoice_list.js"}
```

A value containing `.bundle.` is looked up in the build manifest and resolved to
the hashed output file. A value starting with `/` is emitted as-is — which is how
Theme Studio points at a per-site generated file.

`doctype_js` is additive: your handlers run alongside ERPNext's, they do not
replace them. This is the correct way to add behaviour to a standard form.

### Lifecycle

```python
before_install = "theme_studio.install.before_install"
after_install  = "theme_studio.install.after_install"
after_sync     = "theme_studio.install.after_sync"      # after fixtures sync
after_migrate  = "theme_studio.install.after_migrate"   # after every bench migrate
before_uninstall = "theme_studio.install.before_uninstall"
after_uninstall  = "theme_studio.install.after_uninstall"
```

`after_migrate` is the one that earns its keep in production: Frappe Cloud runs
`bench migrate` on every deploy, so anything that must be recomputed after a code
change goes there. Theme Studio regenerates its stylesheets from it, so a new
version of the CSS compiler reaches the site without anyone re-saving a record.

### Session and request

```python
boot_session = "theme_studio.boot.boot_session"        # add data to frappe.boot
on_session_creation = "app.auth.on_login"
on_logout = "app.auth.on_logout"
update_website_context = "theme_studio.boot.update_website_context"
website_context = {"favicon": "/assets/app/images/favicon.png"}
website_route_rules = [{"from_route": "/orders/<path:name>", "to_route": "order"}]
```

`boot_session` receives the `bootinfo` object and can attach anything JSON-safe.
It lands on `frappe.boot` in the browser. It runs on **every desk load**, so keep
it cheap and cache the result — and wrap it, because an exception here is a
failed login, not a cosmetic bug.

### Document events

```python
doc_events = {
    "Sales Invoice": {
        "validate": "app.overrides.sales_invoice.validate",
        "on_submit": "app.overrides.sales_invoice.on_submit",
    },
    "*": {"on_update": "app.audit.log_change"},   # every doctype; use sparingly
}
```

Handlers receive `(doc, method)`.

### Overrides

```python
override_doctype_class = {"Sales Invoice": "app.overrides.CustomSalesInvoice"}
override_whitelisted_methods = {
    "frappe.desk.doctype.event.event.get_events": "app.calendar.get_events"
}
override_doctype_dashboards = {"Item": "app.dashboards.item_dashboard"}
```

### Scheduler

```python
scheduler_events = {
    "hourly": ["app.tasks.sync_prices"],
    "daily":  ["app.tasks.expire_quotations"],
    "cron":   {"0 2 * * *": ["app.tasks.nightly_reconcile"]},
}
```

### Data lifecycle

```python
fixtures = ["Custom Field", {"dt": "Role", "filters": [["role_name", "like", "Nastiliq%"]]}]
required_apps = ["erpnext"]
app_include_icons = "theme_studio/public/icons.svg"

permission_query_conditions = {"Project": "app.permissions.project_query"}
has_permission = {"Project": "app.permissions.has_project_permission"}

jinja = {"methods": ["app.utils.jinja_methods"], "filters": ["app.utils.jinja_filters"]}
```

### Deliberate omissions are a design statement

Theme Studio's `hooks.py` ends with a comment listing the hooks it does *not*
use — no `doc_events`, no `override_doctype_class`, no overridden methods. That is
what makes it safe to install on a live ERPNext site and clean to uninstall. When
you review a custom app before putting it on a client's production instance, the
override hooks are the first thing to read.

---

## 5. DocTypes

A DocType is a database table, a form, a permission surface and a Python class,
all declared together.

### Standard vs custom

| | Standard DocType | Custom DocType |
|---|---|---|
| Created in | Developer mode, inside an app | Any site, no developer mode |
| Stored as | JSON + `.py` + `.js` files in the app | Rows in the site's database |
| Version controlled | Yes | No |
| Shippable to another site | Yes, with the app | Only via fixtures or export |
| Survives an ERPNext upgrade | Yes | Yes |

For a product you resell, standard DocTypes inside your own app are the only
sensible choice. Custom DocTypes and Customize Form changes live in one site's
database and have to be reapplied by hand on the next one.

### The JSON

```json
{
 "doctype": "DocType",
 "name": "Theme Studio Theme",
 "module": "Theme Studio",
 "autoname": "field:theme_name",
 "engine": "InnoDB",
 "field_order": ["theme_name", "primary_color"],
 "fields": [
  {"fieldname": "theme_name", "fieldtype": "Data", "label": "Theme Name",
   "reqd": 1, "unique": 1, "in_list_view": 1},
  {"fieldname": "primary_color", "fieldtype": "Color", "label": "Accent Colour",
   "default": "#2490ef"}
 ],
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC"
}
```

`field_order` must list exactly the fieldnames in `fields`, in display order. A
mismatch produces fields that silently do not render — worth a one-line check in
CI:

```python
assert dt["field_order"] == [f["fieldname"] for f in dt["fields"]]
```

### Naming

| `autoname` | Result |
|---|---|
| `field:theme_name` | The name *is* that field's value. Good for settings-like records. |
| `INV-.YYYY.-.####` | Series with date and counter. |
| `hash` | Random. Use when nothing is a natural key. |
| `Prompt` | The user types the name. |
| `format:{customer}-{####}` | Template over field values. |
| (blank) | `autoname()` in the controller, or falls back to hash. |

`field:` naming means renaming the record renames the primary key. Set
`allow_rename: 1` and be aware that links to it are updated by Frappe on rename.

### Field types worth knowing

`Data`, `Small Text`, `Text`, `Text Editor`, `Code` (set `options` to a language),
`Markdown Editor`, `Int`, `Float`, `Currency`, `Percent`, `Check`, `Select`
(newline-separated `options`), `Link` (`options` = target DocType), `Dynamic Link`,
`Table` / `Table MultiSelect` (child DocTypes), `Attach`, `Attach Image`, `Color`,
`Date`, `Datetime`, `Time`, `Duration`, `Geolocation`, `JSON`, `Password`,
`Signature`, `Rating`, `Barcode`, `HTML`, `Heading`, and the layout breaks:
`Section Break`, `Column Break`, `Tab Break`, `Fold`.

Useful field properties: `reqd`, `unique`, `read_only`, `hidden`, `no_copy`,
`in_list_view`, `in_standard_filter`, `in_global_search`, `search_index`,
`collapsible`, `precision`, `default`, `description`, `depends_on`,
`mandatory_depends_on`, `read_only_depends_on`, `fetch_from`, `permlevel`.

`depends_on` takes either a fieldname or an eval expression:

```json
{"depends_on": "eval:doc.font_source == 'Google Fonts'"}
```

`fetch_from` pulls a value through a Link without writing a controller:

```json
{"fieldname": "customer_name", "fieldtype": "Data",
 "fetch_from": "customer.customer_name", "read_only": 1}
```

### Singles

`"issingle": 1` makes a settings record. No table is created; values live as rows
in `tabSingles`. Read with `frappe.get_cached_doc("Theme Studio Settings")` or
`frappe.db.get_single_value(dt, field)`.

**Write with `frappe.db.set_single_value(dt, field, value)`, not
`frappe.db.set_value`** — the latter builds an UPDATE against `tab<DocType>`,
which does not exist for a Single. This is a common and confusing bug.

### Child tables

A child DocType sets `"istable": 1` and is referenced from a parent by a `Table`
field whose `options` names it. Children are saved with the parent, have
`parent`/`parenttype`/`parentfield`/`idx` columns, and are never queried on their
own in normal code.

---

## 6. Controllers

`theme_studio_theme.py` defines a class named after the DocType in PascalCase,
subclassing `Document`.

```python
import frappe
from frappe import _
from frappe.model.document import Document

class ThemeStudioTheme(Document):
    def validate(self):
        self.validate_colours()
        self.clamp_numbers()

    def on_update(self):
        self.refresh_site_theme()
```

### Lifecycle order

On insert:
`before_insert` → `autoname` → `before_validate` → `validate` → `before_save` →
*write* → `after_insert` → `on_update`

On update:
`before_validate` → `validate` → `before_save` → *write* → `on_update`

On submit (`docstatus` 0 → 1):
`validate` → `before_submit` → *write* → `on_submit` → `on_update_after_submit`

On cancel (1 → 2): `before_cancel` → *write* → `on_cancel`

On delete: `on_trash` → *delete* → `after_delete`

Two ordering facts that matter in practice:

- `validate` runs on **every** save, insert and update alike. Put invariants
  there, not in `before_insert`.
- `on_trash` runs **before** Frappe checks whether the document is linked
  elsewhere. That is why Theme Studio can clear its own reference out of the
  Settings single in `on_trash` and let the delete proceed.

### Talking to the user

```python
frappe.throw(_("Border colour is not a valid colour."))            # abort, rollback
frappe.throw(_("Not allowed"), frappe.PermissionError)             # typed exception
frappe.msgprint(_("Heads up"), indicator="orange", alert=True)     # non-blocking
```

Always wrap user-facing strings in `_()`. Translation is one of the cheapest
things to get right early and one of the most tedious to retrofit.

Prefer an advisory `msgprint` over a `throw` for anything that is a quality
concern rather than a correctness one. Theme Studio warns about low contrast but
does not block the save — the admin may be halfway through editing, and a form
you cannot save is worse than a theme that needs another pass.

### Flags

```python
doc.flags.ignore_permissions = True
doc.insert(ignore_permissions=True)
doc.save(ignore_version=True)
doc.db_set("status", "Closed")     # direct UPDATE, skips hooks
```

`db_set` is the escape hatch for updating a field without re-running validation —
useful inside `on_update` where a normal `save()` would recurse.

### Reads

```python
frappe.get_doc("Item", "ITEM-0001")          # full document, hits the DB
frappe.get_cached_doc("Item", "ITEM-0001")   # from Redis when warm
frappe.db.get_value("Item", name, "item_name")
frappe.db.get_value("Item", {"item_code": x}, ["item_name", "stock_uom"], as_dict=True)
frappe.get_all("Item", filters={"disabled": 0}, fields=["name"], limit=20)
frappe.db.exists("Item", name)
frappe.db.count("Item", {"disabled": 0})
```

`frappe.get_all` ignores permissions; `frappe.get_list` applies them. Use
`get_list` for anything reachable from a user request, `get_all` for internal
logic where you have already decided access.

### The query builder

```python
from frappe.query_builder import DocType
Item = DocType("Item")
rows = (frappe.qb.from_(Item)
        .select(Item.name, Item.item_name)
        .where(Item.disabled == 0)
        .limit(20)).run(as_dict=True)
```

Prefer this over `frappe.db.sql` with f-strings. If you must write raw SQL, use
parameters (`%(name)s` with a dict), never string interpolation.

---

## 7. Client scripts

`theme_studio_theme.js` sits next to the controller and is loaded automatically
with the form.

```javascript
frappe.ui.form.on("Theme Studio Theme", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Apply to Site"), () => apply(frm)).addClass("btn-primary");
        frm.dashboard.set_headline(__("Saved but not applied."));
    },
    primary_color(frm) {
        // fires when that field changes
    },
    validate(frm) {
        // client-side check; return false to block
    },
});
```

Child table events use `frappe.ui.form.on("Child DocType", {...})` with handlers
receiving `(frm, cdt, cdn)`.

Common `frm` operations:

```javascript
frm.set_value("field", value);
frm.set_df_property("field", "hidden", 1);
frm.toggle_display("field", condition);
frm.set_query("item_code", () => ({ filters: { disabled: 0 } }));
frm.refresh_field("items");
frm.copy_doc();
frm.reload_doc();
```

Calling the server:

```javascript
frappe.call({
    method: "theme_studio.api.apply_theme",
    args: { name: frm.doc.name },
    freeze: true,
    freeze_message: __("Applying theme..."),
    callback: (r) => { if (r.message) frappe.show_alert({message: __("Done"), indicator: "green"}); },
});
```

Dialogs, uploads, confirms:

```javascript
const d = new frappe.ui.Dialog({
    title: __("Start from a preset"),
    fields: [{ fieldname: "preset", fieldtype: "Select", label: __("Preset"),
               options: ["A", "B"], reqd: 1 }],
    primary_action_label: __("Create"),
    primary_action(values) { d.hide(); /* ... */ },
});
d.show();

new frappe.ui.FileUploader({
    dialog_title: __("Import theme file"),
    restrictions: { allowed_file_types: [".json"] },
    on_success(file_doc) { /* file_doc.file_url */ },
});

frappe.confirm(__("Are you sure?"), () => { /* yes */ });
```

Escape anything user-supplied that you interpolate into markup:
`frappe.utils.escape_html(value)`.

### Client Script records vs app files

The **Client Script** DocType lets you add JS to a form from the UI, stored in
that site's database. Fine for a one-off tweak on one client's site; wrong for
anything you ship, because it is not version controlled and does not travel with
the app. Anything you would reuse belongs in the app as a file.

---

## 8. Server-side API

### Whitelisted methods

```python
@frappe.whitelist()
def apply_theme(name: str):
    ...

@frappe.whitelist(allow_guest=True)
def public_thing():
    ...

@frappe.whitelist(methods=["POST"])
def mutating_thing():
    ...
```

Callable at `/api/method/theme_studio.api.apply_theme`.

Three rules, all of which have burned real deployments:

1. **Assume every argument is a string.** Frappe passes HTTP parameters through as
   strings; `int(x or 0)` and `frappe.parse_json(x)` before you trust anything.
2. **Check permissions yourself.** `@frappe.whitelist()` means "any logged-in
   user", not "any authorised user". If the method does something privileged, say
   so explicitly:

   ```python
   if "System Manager" not in frappe.get_roles():
       frappe.throw(_("Not permitted"), frappe.PermissionError)
   ```

3. **Never pass a user-supplied string to `frappe.get_attr`, `eval`, or a path
   join.** Theme Studio's preset loader rejects anything containing a path
   separator before touching the filesystem.

### Returning a file download

```python
frappe.response["filename"] = "theme.json"
frappe.response["filecontent"] = json.dumps(payload, indent=2)
frappe.response["type"] = "download"
```

From the browser, open the URL directly rather than using `frappe.call` — the
session cookie goes along:

```javascript
window.open("/api/method/theme_studio.api.export_theme?name=" + encodeURIComponent(name));
```

### REST API

Every DocType is exposed without writing any code.

```
GET    /api/v2/document/Item
GET    /api/v2/document/Item/ITEM-0001
POST   /api/v2/document/Item
PUT    /api/v2/document/Item/ITEM-0001
DELETE /api/v2/document/Item/ITEM-0001
```

Authenticate with an API key/secret pair generated on a User record:

```
Authorization: token <api_key>:<api_secret>
```

v1 (`/api/resource/...`) still works. v2 returns a consistent envelope and
clearer errors; prefer it for new integrations.

### Realtime

```python
frappe.publish_realtime("theme_studio:updated", {"hash": h}, after_commit=True)
```

```javascript
frappe.realtime.on("theme_studio:updated", (data) => { /* ... */ });
```

With no `user` or `doctype` argument the message goes to the whole site. Use
`after_commit=True` so subscribers are not told about a change that then rolls
back. Treat realtime as a nicety, never as the only path — the socketio process
can be down and the rest of the site will carry on working.

---

## 9. Extending other apps

In rough order of preference:

**1. Add, do not replace.** `doctype_js` layers your handlers onto an existing
form. `doc_events` adds a `validate` alongside ERPNext's. Neither breaks when
upstream changes its own implementation.

```python
doc_events = {"Sales Invoice": {"validate": "app.overrides.si.validate"}}
```

**2. Custom Fields via fixtures.** Add fields to a standard DocType without
touching its JSON, and ship them:

```python
fixtures = [{"dt": "Custom Field", "filters": [["name", "like", "%-nastiliq_%"]]}]
```

Name your custom fields with a consistent prefix so the filter is reliable and you
never export another app's fields by accident.

**3. Property Setter.** What "Customize Form" writes. Changes a property of an
existing field (label, hidden, reqd) without redefining it. Also fixture-able.

**4. `override_doctype_class`.** Subclass the controller and replace it. Powerful,
and it breaks loudly when the parent class changes:

```python
# hooks.py
override_doctype_class = {"Sales Invoice": "app.overrides.CustomSalesInvoice"}

# app/overrides.py
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

class CustomSalesInvoice(SalesInvoice):
    def validate(self):
        super().validate()
        self.our_extra_check()
```

Only one app can override a given class. Two apps both overriding Sales Invoice
is a conflict you will discover at the worst moment.

**5. `override_whitelisted_methods`.** Replace a specific endpoint. Narrower than
a class override, and useful when you need to change one API's behaviour.

**6. Monkey patching in `__init__.py`.** Works. Do not. It is invisible to anyone
reading the app later, and it is the single most common cause of "the upgrade
broke everything and nobody knows why".

---

## 10. Assets and the build system

Files in `<app>/public/` are served at `/assets/<app_name>/`. In development
they are symlinked, so an edit is live on refresh.

```
theme_studio/public/js/theme_studio.bundle.js  →  /assets/theme_studio/js/theme_studio.bundle.js
```

### Bundles

A file named `*.bundle.js` or `*.bundle.css` is processed by esbuild into a
hashed output recorded in `sites/assets/assets.json`. A hook value containing
`.bundle.` is resolved through that manifest, which is what gives you
cache-busting for free.

```bash
bench build --app theme_studio        # build once
bench build --app theme_studio --force
bench watch                           # rebuild on change, development only
```

Import other files into a bundle with normal ES module syntax; esbuild resolves
them.

### Where to put styles

Three options, and the choice matters more than it looks:

| Approach | When |
|---|---|
| `.bundle.css` in `public/css` | Styling that is the same on every site. Built at deploy, cached hard. |
| CSS custom property overrides | Theming. Frappe paints the desk from custom properties; re-pointing them themes every page at once, including pages shipped in a future release. |
| A per-site generated file under `/files/` | Values that differ per site. The hook path is static but resolves inside each site's own `public/files`. |

Theme Studio uses the second and third together. It is worth understanding why the
second beats writing component selectors: a rule targeting `.list-row-container`
breaks when upstream renames the class, but `--bg-color` has survived several
major versions, and setting it themes list views you have never seen.

### Icons

```python
app_include_icons = "theme_studio/public/icons.svg"
```

An SVG sprite of `<symbol id="icon-foo">` elements, usable as
`<svg><use href="#icon-foo"></use></svg>` and referencable by name in workspace
and DocType `icon` fields.

---

## 11. Desk presence: workspaces and the apps screen

Two separate things have to be right or your app is invisible.

### Workspace

A `Workspace` record, shipped as
`<module>/workspace/<name>/<name>.json`, defines the page users land on.

```json
{
 "doctype": "Workspace",
 "name": "Theme Studio",
 "label": "Theme Studio",
 "module": "Theme Studio",
 "public": 1,
 "icon": "palette",
 "content": "[{\"id\":\"h\",\"type\":\"header\",\"data\":{\"text\":\"...\",\"col\":12}}]",
 "links": [
  {"type": "Card Break", "label": "Themes", "link_count": 1},
  {"type": "Link", "label": "Themes", "link_to": "Theme Studio Theme", "link_type": "DocType"}
 ],
 "shortcuts": [
  {"type": "DocType", "label": "Themes", "link_to": "Theme Studio Theme", "color": "Blue"}
 ]
}
```

`content` is a JSON string *inside* the JSON — a serialised block layout. Generate
it with `json.dumps` rather than hand-escaping; that is what the build script in
this repo does. `Card Break` entries group the `Link` entries that follow them,
and each `Card Break`'s `link_count` must equal the number of links under it.

### Apps screen

```python
add_to_apps_screen = [
    {
        "name": "theme_studio",
        "logo": "/assets/theme_studio/images/theme_studio.svg",
        "title": "Theme Studio",
        "route": "/app/theme-studio",
        "has_permission": "theme_studio.api.has_app_permission",
    }
]
```

`has_permission` is a dotted path to a function returning a boolean — it decides
who sees the icon.

### v15 → v16 changes to be aware of

- The desk moved from `/app` to `/desk`. Old `/app` routes redirect, but
  hard-coded `/app/...` strings in your own code are worth auditing.
- The `/apps` page is deprecated, replaced by a desktop screen that is
  auto-generated from public workspaces — and generated correctly only if
  `add_to_apps_screen` is present and right.
- Modifications made to *standard* workspaces (Selling, Buying) are lost on
  upgrade. Copy their content to the clipboard before migrating, or better: ship
  your own workspace instead of editing theirs.
- Several modules moved out of core into separate apps (Newsletter, Blog, Energy
  Points among them). If you depended on one, add it to `required_apps`.

---

## 12. Fixtures, patches and migrations

### Schema migrations

`bench migrate` diffs your DocType JSON against the live tables and applies the
difference: added columns, changed types, new indexes. You do not write schema
migrations by hand. Adding a field to the JSON and running migrate is the whole
process.

### Fixtures

Data records that ship with the app.

```python
fixtures = [
    "Custom Field",
    {"dt": "Role", "filters": [["role_name", "like", "Nastiliq%"]]},
]
```

```bash
bench --site dev.local export-fixtures      # app/fixtures/*.json
```

Fixtures are re-imported on every migrate, which makes them an overwrite: if a
client edits a record you ship as a fixture, your next deploy reverts their edit.
Ship configuration as fixtures; ship anything a client is meant to own as a
one-time `after_install` insert instead. Theme Studio creates its starter theme in
`after_install` precisely so a client can edit or delete it and have that stick.

### Patches

One-time data migrations, listed in `patches.txt` and run once per site, tracked
in the `Patch Log` table.

```
[pre_model_sync]
theme_studio.patches.v1_0.rename_old_field

[post_model_sync]
theme_studio.patches.v1_1.backfill_generated_css
```

`pre_model_sync` runs before the schema diff (when you need the old shape);
`post_model_sync` after (the usual case).

```python
# theme_studio/patches/v1_1/backfill_generated_css.py
import frappe

def execute():
    for name in frappe.get_all("Theme Studio Theme", pluck="name"):
        doc = frappe.get_doc("Theme Studio Theme", name)
        doc.save(ignore_permissions=True)
```

Patches must be idempotent — a re-run after a failed migrate must not double
anything. Never delete a patch line once shipped; sites that have not run it yet
still need it.

---

## 13. Background jobs and the scheduler

```python
frappe.enqueue(
    "theme_studio.tasks.rebuild_all",
    queue="short",        # short (default) | default | long
    timeout=300,
    is_async=True,
    job_name="rebuild themes",
    theme="Ledger Light", # kwargs pass through
)
```

Queued work runs in a worker process with its own database connection. Two
consequences: the job must commit its own changes, and it cannot see uncommitted
state from the request that enqueued it. `enqueue_after_commit=True` avoids
enqueueing work for a transaction that then rolls back.

Scheduled jobs come from `scheduler_events` in hooks and appear as `Scheduled Job
Type` records you can inspect and disable per site. Check the scheduler is
actually running before debugging a job that "never fires":

```bash
bench --site dev.local doctor
bench --site dev.local enable-scheduler
```

---

## 14. Permissions

Layers, applied in this order:

1. **Role permissions** — the `permissions` array on the DocType. Per role:
   read/write/create/delete/submit/cancel/amend/report/export/share/print/email.
2. **Permlevel** — set `permlevel: 1` on a field and add a second permissions row
   for level 1. Field-level access, useful for cost prices and approval fields.
3. **User Permissions** — restrict a user to specific records of a linked DocType
   (a Company, a Warehouse). Applied automatically to every query.
4. **`permission_query_conditions`** — a hook returning a SQL `WHERE` fragment,
   for logic the declarative layers cannot express.
5. **`has_permission`** — a hook returning a boolean for a single document.

```python
# hooks.py
permission_query_conditions = {"Project": "app.permissions.project_query"}
has_permission = {"Project": "app.permissions.has_project_permission"}

# app/permissions.py
def project_query(user=None):
    user = user or frappe.session.user
    return f"`tabProject`.owner = {frappe.db.escape(user)}"

def has_project_permission(doc, user=None, permission_type=None):
    return doc.owner == (user or frappe.session.user)
```

Check in Python with `frappe.has_permission("Project", "write", doc)`.

Remember that none of this applies to `@frappe.whitelist()` methods unless you
invoke it. The decorator authenticates; it does not authorise.

---

## 15. Testing

```python
# theme_studio/theme_studio/doctype/theme_studio_theme/test_theme_studio_theme.py
import frappe
from frappe.tests.utils import FrappeTestCase

class TestThemeStudioTheme(FrappeTestCase):
    def test_invalid_colour_is_rejected(self):
        doc = frappe.get_doc({
            "doctype": "Theme Studio Theme",
            "theme_name": "Broken",
            "primary_color": "not-a-colour",
        })
        self.assertRaises(frappe.ValidationError, doc.insert)
```

```bash
bench --site test.local run-tests --app theme_studio
bench --site test.local run-tests --doctype "Theme Studio Theme"
```

`FrappeTestCase` rolls back after each test. Test records for dependencies come
from `test_records.json` next to each DocType.

**Separate the pure logic.** Theme Studio's colour maths and CSS compiler import
no Frappe at all, so they can be exercised with plain `python3` in a second, with
no site, no database and no bench. Everything that does not need the framework is
much cheaper to test when it does not import the framework — and that pressure
tends to produce a better-factored app.

---

## 16. Deployment

### Development

```bash
bench start                                   # all processes via Procfile
bench --site dev.local set-config developer_mode 1
bench --site dev.local clear-cache
bench build --app theme_studio
```

### Self-hosted production

```bash
cd ~/frappe-bench/apps/theme_studio && git pull
cd ~/frappe-bench
bench --site client.local migrate
bench build --app theme_studio
bench restart
```

Take a backup first, every time:
`bench --site client.local backup --with-files`.

### Frappe Cloud

1. `pyproject.toml` at the repo root; package directory named exactly like
   `app_name`. Both already correct in this repo.
2. Push to GitHub. Private repos work once you connect the repo to your Frappe
   Cloud account.
3. Bench group → **Apps** → **Add App** → **From GitHub** → repo and branch.
4. **Deploy**. Frappe Cloud builds a new image, runs `bench build` and
   `bench migrate`, and swaps it in.
5. Site → **Apps** → install the app on each site.

What Frappe Cloud does *not* give you:

- No shell on the app server, so no `bench console` for ad-hoc fixes. Anything
  you might need to run has to exist as a whitelisted method, a patch, or a
  scheduled job. Plan for this before you need it at 2am.
- No developer mode. Schema changes only arrive through a deploy.
- Deploys are per bench group. Every site in the group gets the new code at once.
  Give a client with a bespoke build their own group.

### Versioning

Bump `__version__` in `theme_studio/__init__.py` and tag the commit. Frappe Cloud
deploys from a branch, so the discipline that actually matters is: a branch per
release channel (`main` for your demo instance, `stable` for client benches), and
clients pinned to `stable`.

---

## 17. Staying upgrade-safe as a reseller

The thing that determines whether a white-labelled ERPNext is a product or a
liability is how much of your customisation survives an upstream major version.
Ranked by how well each holds up:

**Safest — your own DocTypes in your own app.** Nothing upstream touches them.
Migrate as normal.

**Safe — CSS custom property overrides.** Frappe has kept its custom property
names across several major versions. When v16 introduced the Espresso token
family it *added* it rather than removing the old one. Setting variables is the
single most durable way to restyle the desk.

**Mostly safe — Custom Fields and Property Setters shipped as fixtures.** They
survive upgrades. They break if upstream removes the field you attached to, which
is rare and shows up immediately.

**Needs review each upgrade — `doc_events` and `doctype_js`.** Your code still
runs, but the surrounding logic may have changed underneath it. Read the release
notes for the doctypes you hook.

**Needs work each upgrade — `override_doctype_class`.** You have taken on a
subclass of code you do not control. Every major version, re-read the parent's
method you overrode.

**Breaks — component CSS selectors, monkey patches, and edits to standard
workspaces.** Selectors get renamed (v15's `.desk-sidebar` is v16's
`.body-sidebar`). Standard workspace modifications are explicitly discarded on
upgrade to v16. Keep this layer as thin as you can and make it easy to find:
Theme Studio confines every selector to one named constant, `COMPONENT_RULES`, so
an upgrade review is one block of code rather than a search across the app.

**Never fork the framework.** A fork means maintaining both ERPNext and Frappe
Framework alone while upstream keeps shipping. The whole value of building on
ERPNext is the upstream release cadence; a fork spends it.

Practical checklist per upgrade:

```bash
# on a clone of the client's site, never in place
bench --site staging.local backup --with-files
# switch the bench to the new version, then:
bench --site staging.local migrate
bench --site staging.local run-tests --app theme_studio
```

Then click through your own app, then the client's three most-used workflows.

---

## 18. Pitfalls

1. **`field_order` out of sync with `fields`.** Fields silently do not render.
2. **`frappe.db.set_value` on a Single.** Use `set_single_value`.
3. **Missing `__init__.py`** in `doctype/` or a doctype folder. Reads as a
   framework import bug; it is a missing file.
4. **Module not in `modules.txt`.** Migrate refuses to import the DocType.
5. **Assuming request arguments are typed.** They are strings. Cast them.
6. **`@frappe.whitelist()` treated as an authorisation check.** It is not.
7. **`frappe.get_all` where `frappe.get_list` was meant.** `get_all` ignores
   permissions.
8. **Un-cached work in `boot_session`.** It runs on every desk load.
9. **Unhandled exceptions in `boot_session` or `update_website_context`.** These
   run in the login path; an exception is an outage, not a cosmetic bug.
10. **Developer mode on production.** Schema edits get written into `apps/` on a
    live site.
11. **Fixtures used for client-owned data.** Every deploy overwrites their edits.
12. **Editing standard workspaces.** Lost on upgrade.
13. **Assets not rebuilt after deploy.** `bench build --app <app>`, then a hard
    refresh; stale bundles produce bugs that do not reproduce locally.
14. **Non-idempotent patches.** A failed migrate re-runs them.
15. **Two apps overriding the same doctype class.** One silently wins.
16. **Forgetting `bench --site <site> clear-cache`** after changing hooks. Hooks
    are cached per site.
17. **Hard-coding `/app/...` routes.** v16 serves the desk from `/desk`.
18. **Shipping a theme or config that can execute JavaScript.** The moment you
    accept files from anyone but yourself, that is remote code execution.

---

## 19. Command reference

```bash
# apps and sites
bench new-app <app>
bench get-app <app> <git-url>
bench new-site <site>
bench --site <site> install-app <app>
bench --site <site> uninstall-app <app>
bench --site <site> list-apps
bench drop-site <site>

# development
bench start
bench --site <site> set-config developer_mode 1
bench --site <site> clear-cache
bench --site <site> clear-website-cache
bench build --app <app>
bench watch
bench restart

# data
bench --site <site> migrate
bench --site <site> backup --with-files
bench --site <site> restore <path> --with-public-files <p> --with-private-files <p>
bench --site <site> export-fixtures
bench --site <site> set-value <doctype> <name> <field> <value>

# debugging
bench --site <site> console
bench --site <site> mariadb
bench --site <site> doctor
bench --site <site> show-config
bench --site <site> run-tests --app <app>

# users
bench --site <site> add-system-manager <email>
bench --site <site> set-admin-password <password>
```

---

## Further reading

- Framework docs — <https://docs.frappe.io/framework>
- Hooks reference — <https://docs.frappe.io/framework/user/en/python-api/hooks>
- v16 migration guide — <https://github.com/frappe/frappe/wiki/Migrating-to-version-16>
- Espresso design system — <https://frappe.io/design/espresso>
- Frappe Cloud docs — <https://docs.frappe.io/cloud>

The single best reference remains the Frappe and ERPNext source. When you want to
know how something really behaves, `bench --site <site> console` plus reading the
relevant file in `apps/frappe/frappe/` beats searching the forum.
