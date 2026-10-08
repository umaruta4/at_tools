# AT Tools Development Guide

AT Tools is a collection of tools for ERPNext/HRMS. Each tool is its own **Frappe module**, and can be enabled or disabled per site.

## 1. Folder Structure

Paths below are relative to the repo root (`apps/at_tools/`). Note there are three levels of `at_tools`: the root repo, the app package, and the core module.

```
at_tools/                              # repo root (git)
├── README.md
├── docs/DEVELOPMENT.md                # this document
├── pyproject.toml
└── at_tools/                          # app package (hooks.py lives here)
    ├── hooks.py                       # only reads sites/.at_tools/generated_hooks.json, don't add hooks here
    ├── tools.py                       # TOOLS registry, is_tool_enabled(), collect_hooks(), generate_hooks()
    ├── modules.txt                    # list of Frappe modules (AT Tools, User Permission Tools, ...)
    ├── public/js/<module>/<app>/      # per-module form JS, split by target app
    │   └── user_permission_tools/erpnext/employee.js
    ├── at_tools/                      # "AT Tools" module (core / settings)
    │   └── doctype/
    │       ├── at_tools_settings/     # Single DocType: tool list + per-site activation
    │       └── at_tool_setting/       # child table row for a tool
    └── user_permission_tools/          # one folder per tool
        ├── hooks.py                   # HOOKS owned by this tool (doc_events, doctype_js, ...)
        ├── install.py                 # install(): runs when the tool is enabled on a site
        ├── utils.py                   # helpers: sync, get_template_items, is_enabled
        ├── doc_events/
        │   └── erpnext/employee.py    # doc_events handler, split by the DocType's owning app
        └── doctype/                   # DocTypes owned by this tool
```

### Placement rules

| What you're building | Where it goes |
|---|---|
| New module/tool | Folder `at_tools/at_tools/<module_name>/` (next to `hooks.py`) |
| DocType owned by a tool | `<module>/doctype/<doctype_name>/` |
| Hooks (doc_events, doctype_js, etc.) | `<module>/hooks.py`, `HOOKS` variable |
| `doc_events` handler | `<module>/doc_events/<owning_app>/<doctype>.py` |
| Form JS | `at_tools/public/js/<module>/<target_app>/<doctype>.js` |
| Install logic (custom fields, etc.) | `<module>/install.py`, `install()` function |
| Whitelisted methods for a Page | `<module>/page/<page_name>/<page_name>.py`, next to that page's `.js`/`.json` (same convention as `frappe.core.page.permission_manager`) |

Example: the Employee handler for ERPNext lives at `doc_events/erpnext/employee.py`; if an event for an HRMS-owned DocType comes up later, put it in `doc_events/hrms/`.

## 2. Tool Registry (`tools.py`)

Every tool must be registered in `TOOLS`:

```python
TOOLS = {
	"User Permission Tools": {
		"install": "at_tools.user_permission_tools.install.install",
		"hooks": "at_tools.user_permission_tools.hooks",
	},
}
```

- **Key** is the Frappe module name (same as the one in `modules.txt`). This key is used as the tool name in `is_tool_enabled()` and in AT Tools Settings.
- **`install`** (optional): function called **once** when the tool is enabled on a site. Used for custom fields, initial data, and so on.
- **`hooks`** (optional): module with a `HOOKS` variable. Collected into the generated hooks data file.

A new tool **must** also be added to `modules.txt`, so Frappe recognizes the module.

## 3. Per-Site Activation

Active status is stored in the Single DocType **AT Tools Settings**, so it applies per site (each site has its own database).

An admin (System Manager) enables a tool from **AT Tools Settings** by checking the `Enabled` column. When a tool flips from disabled to enabled, `install()` runs automatically.

Disabling a tool does **not** remove custom fields or data that was already created.

## 4. The `is_tool_enabled(tool)` Function

Location: `at_tools/tools.py`

```python
from at_tools.tools import is_tool_enabled

is_tool_enabled("User Permission Tools")  # True / False
```

This function reads AT Tools Settings for the currently active site, then checks whether the `tool` row is `enabled`.

### When to use it

Use it at **every entry point** of a tool, because hooks registered in the generated hooks file apply globally to all sites, not just the site that enabled the tool:

- **`doc_events` handlers**: check at the start of the function, then `return` if disabled.
- **Scheduler, background jobs, and whitelisted APIs**: check at the start too.
- **Functions called from a handler**: it's enough to check at the entry point.

### Usage example

```python
# doc_events/erpnext/employee.py
from at_tools.tools import is_tool_enabled
from at_tools.user_permission_tools.utils import sync_employee_user_permissions


def on_update(doc, method=None):
	if not is_tool_enabled("User Permission Tools"):
		return

	sync_employee_user_permissions(doc)
```

`user_permission_tools/utils.py` has an `is_enabled()` wrapper that already calls `is_tool_enabled("User Permission Tools")`. Use this wrapper when you're inside that same tool.

### Notes

- `is_tool_enabled` reads the Single DocType on every call, so one check per handler is enough — don't check it on every line.
- Don't use a tool name that isn't in `TOOLS`. This function silently returns `False` with no error, which can easily hide a typo.

## 5. Per-Module Hooks (`HOOKS`)

Each module defines its hooks in its own `hooks.py`:

```python
# user_permission_tools/hooks.py
HOOKS = {
	"doc_events": {
		"Employee": {
			"on_update": "at_tools.user_permission_tools.doc_events.erpnext.employee.on_update",
		},
	},
	"doctype_js": {
		"Employee": "public/js/user_permission_tools/erpnext/employee.js",
	},
}
```

Supported keys are the same as regular Frappe hooks: `doc_events`, `doctype_js`, `doctype_list_js`, `scheduler_events`, and others.

### Hooks flow

1. The developer writes `HOOKS` in `<module>/hooks.py`.
2. An admin clicks **Generate Hooks** in AT Tools Settings.
3. `collect_hooks()` gathers `HOOKS` from tools that are **enabled** on that site.
4. The result is written to `sites/.at_tools/generated_hooks.json` (via `generate_hooks()` in `tools.py`).
5. `at_tools/hooks.py` reads that JSON file via `load_generated_hooks()`, and Frappe uses it.

If two tools register the same hook (e.g. two handlers for `Employee.on_update`), the results are merged into a deduplicated list.

**Restart bench after generating**, because hooks are read at process start. If a hook doesn't change even after restarting, run `bench --site <site> clear-cache`.

### Why a data file instead of a committed `.py`

`sites/.at_tools/generated_hooks.json` is **deliberately absent from the `at_tools` repo** — `sites/` is entirely outside this app's repo (not just `.gitignore`d), so it can never be committed. Reasons:

- `sites/` is the bench data directory that persists across deploys; `apps/` (including this repo) gets replaced on every `git pull`/deploy, so generated output that used to be stored inside the app package would be lost unless manually committed every time.
- JSON is a safer format for an auto-generated file (read with `json.load`, not `exec`/importing a Python module).

Consequence: **a new deployment (fresh clone / new server) must click Generate Hooks once** after the site is migrated, since the data file doesn't come along with the clone. This replaces the old note "generated_hooks.py must be committed".

## 6. Creating a New Tool: Checklist

1. Create the folder `at_tools/at_tools/<module_name>/` with `__init__.py`.
2. Add the module name to `modules.txt`.
3. Add the DocType under `<module>/doctype/` with `module` = the module name.
4. If a custom field is needed, write it in `<module>/install.py` with an `install()` function, using `create_custom_fields(..., update=True)`.
5. Register it in `TOOLS` (`tools.py`) with the module name as key, plus `install` and `hooks`.
6. Create `<module>/hooks.py` with a `HOOKS` variable.
7. Write the handler in `<module>/doc_events/<app>/<doctype>.py`, and check `is_tool_enabled()` at the start of the function.
8. If there's JS, put it at `at_tools/public/js/<module>/<app>/<doctype>.js`, then register it in `HOOKS["doctype_js"]`.
9. Migrate: `bench --site <site> migrate`.
10. In AT Tools Settings: enable the tool, then click **Generate Hooks**.
11. Run `bench build --app at_tools` if there's new JS, then restart bench.

## 7. Things to Remember

- **Install doesn't re-run automatically.** `install()` only runs when a tool is first enabled. If you add a field to `install()` for a site where the tool is already active, disable and re-enable the tool, or call `install()` manually.
- **`sites/.at_tools/generated_hooks.json` doesn't come along with a clone/deploy.** A new deployment (or new site) must click **Generate Hooks** once after enabling the tool, before hooks will work.
- **Generate reads the tools enabled on the site where the button was clicked.** This file is used bench-wide, so if several sites have different settings, the result may not match for other sites. Handlers still check `is_tool_enabled`, so a disabled tool won't run.
- **An error in a `doc_events` handler cancels the document's save.** The User Permission sync handler runs inside the Employee save transaction, so an error there will cancel the save. Validate input at the template level (`validate`) as much as possible, not during sync.
- **`modified` must not change during sync.** Use `frappe.db.set_value(..., update_modified=False)` in handlers that write to the document currently being saved, so the next save from the form doesn't hit a `TimestampMismatchError`.
- **The `name` field (Employee ID) can only be used with Allow = Employee** in User Permission Template.
- **ERPNext automatically creates a User Permission** for an Employee with a `user_id`: `Company = <company>` and `Employee = <self>`. The sync tool never recreates existing UPs, and never deletes them.
