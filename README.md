### AT Tools

AT Tools is a collection of tools for ERPNext/HRMS. Each tool is its own Frappe module and can be enabled or disabled per site from **AT Tools Settings** — so a site only carries the tools it actually needs.

### Tools

#### User Permission Tools

Automates `User Permission` records for Users instead of creating them by hand one by one.

- **User Permission Template**: define a reusable set of rules — which DocType to restrict (`Allow`), where the value comes from (a fixed value, or copied live from a field on the User's linked Employee, such as Department, Branch, or Cost Center), whether it applies to all document types or only to specific ones (filtered to DocTypes that actually link to the `Allow` DocType, the same way core's `User Permission` does it).
- **User Permission Setting**: assign a template (or define rows directly) for a specific **User**. On every save, that User's `User Permission` records are reconciled to match it — created, kept, or removed as needed — while any `User Permission` created manually (or by ERPNext itself) is left untouched. A row whose value comes from an Employee field requires the User to actually have a linked Employee; saving with no such Employee throws an error instead of silently skipping the row.

#### Role Permission Enhancer Tools

A faster, more complete way to inspect and edit DocType permissions than core's Role Permissions Manager, plus two read-only checkers for sanity-checking access before relying on it.

- **Enhanced Role Permission Manager** (`enhanced-role-permission-manager`): filter by DocType and/or Role to see the effective permission table (standard + custom rules merged), then **Set** a role's permissions, **Add A New Rule**, **Remove** a rule, or open **Linked DocTypes** to grant/revoke permissions in bulk across every DocType the target links to (direct Link fields and Link fields inside child tables) — a bulk workflow core's Role Permissions Manager doesn't have.
- **User Access Checker** (`user-access-checker`): pick a User and a DocType to see, at a glance, whether that user can actually use it end-to-end — covers the target DocType, every DocType it links to, and every related module Settings (Single) DocType, with rows missing Read access highlighted.
- **Role Profile Access Checker** (`role-profile-access-checker`): the same idea, keyed on a Role Profile instead of a single User. Pick a Role Profile alone to see every DocType its roles can access; add a DocType on top of that to get the same detailed breakdown as the User Access Checker.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app at_tools
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/at_tools
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit

### Development Documentation

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the module structure, tool registry, hooks, and how to use `is_tool_enabled`.
