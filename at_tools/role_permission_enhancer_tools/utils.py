import frappe
from frappe import _
from frappe.core.doctype.custom_docperm.custom_docperm import update_custom_docperm
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.permissions import add_permission, get_all_perms, setup_custom_perms

from at_tools.tools import is_tool_enabled

TOOL = "Role Permission Enhancer Tools"

PTYPES = [
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"import",
	"export",
	"share",
]

# Frappe only honors read/write at permlevel > 0 (field-level permissions); the other
# ptypes only make sense at permlevel 0. Mirrors frappe.core.page.permission_manager.
LEVEL_PTYPES = ["read", "write"]


def check_access():
	"""Shared access gate for every whitelisted method of this module's pages."""
	frappe.only_for("System Manager")
	if not is_tool_enabled(TOOL):
		frappe.throw(_("{0} is not enabled in AT Tools Settings").format(TOOL))


def find_linked_doctypes(doctype):
	"""DocTypes needed to access `doctype`: direct Link fields + Link fields inside
	Table (child) fields, depth 1."""
	result = {}

	def add(linked, via, kind):
		if linked == doctype or linked in result or not frappe.db.exists("DocType", linked):
			return
		result[linked] = {"doctype": linked, "via": via, "kind": kind}

	for field in frappe.get_meta(doctype).fields:
		if field.fieldtype == "Link" and field.options:
			add(field.options, field.fieldname, "Link")
		elif field.fieldtype == "Table" and field.options:
			for child_field in frappe.get_meta(field.options).fields:
				if child_field.fieldtype == "Link" and child_field.options:
					add(child_field.options, f"{field.fieldname} > {child_field.fieldname}", "Table")

	return list(result.values())


def find_related_settings(doctype, linked_doctypes):
	"""Single (Settings) DocTypes belonging to any module touched by `doctype` or its linked
	doctypes - e.g. Purchase Order (module Buying) links to Item (module Stock), so both
	Buying Settings and Stock Settings count as related."""
	modules = {frappe.get_meta(doctype).module}
	modules.update(frappe.get_meta(item["doctype"]).module for item in linked_doctypes)
	modules.discard(None)

	exclude = {doctype} | {item["doctype"] for item in linked_doctypes}
	return [
		d
		for d in frappe.get_all(
			"DocType",
			filters={"module": ["in", sorted(modules)], "issingle": 1},
			fields=["name", "module"],
			order_by="module, name",
		)
		if d.name not in exclude
	]


def get_roles_permissions(doctype, roles, permlevel=0):
	"""Effective ptype access for the given `roles` on `doctype` at `permlevel`, merged (OR-ed).
	Document-level only - ignores if_owner and per-document User Permission restrictions."""
	roles = set(roles)
	perms = {ptype: 0 for ptype in PTYPES}
	for perm in frappe.get_meta(doctype).permissions:
		if perm.role in roles and (perm.permlevel or 0) == permlevel:
			for ptype in PTYPES:
				if perm.get(ptype):
					perms[ptype] = 1
	return perms


def get_role_profile_roles(role_profile):
	"""Roles assigned to a Role Profile (its `roles` child table, by role name)."""
	return frappe.get_all("Has Role", filters={"parenttype": "Role Profile", "parent": role_profile}, pluck="role")


def get_roles_accessible_doctypes(roles, permlevel=0):
	"""Every DocType where any of `roles` has at least Read access at `permlevel`, with ptypes
	merged (OR-ed) across those roles. Built from frappe.permissions.get_all_perms per role
	(standard + custom perms, 2 queries each) rather than loading every DocType's meta, since
	this has no target doctype to narrow down - e.g. used for a Role Profile's "what can it
	access" overview, before a specific doctype is picked."""
	merged = {}
	for role in set(roles):
		for perm in get_all_perms(role):
			if (perm.permlevel or 0) != permlevel or not perm.get("read"):
				continue
			row = merged.setdefault(perm.parent, {ptype: 0 for ptype in PTYPES})
			for ptype in PTYPES:
				if perm.get(ptype):
					row[ptype] = 1

	if not merged:
		return []

	# Custom DocPerm rows can outlive a deleted DocType; drop anything that no longer exists.
	modules = {
		d.name: d.module
		for d in frappe.get_all("DocType", filters={"name": ["in", list(merged)]}, fields=["name", "module"])
	}
	return sorted(
		(
			{"doctype": name, "module": modules.get(name), **ptypes}
			for name, ptypes in merged.items()
			if name in modules
		),
		key=lambda row: (row["module"] or "", row["doctype"]),
	)


def _ensure_custom_docperm(doctype, role, permlevel):
	"""Copy standard DocPerm to Custom DocPerm if this doctype has none yet (same as Role
	Permission Manager), then make sure a row exists for this role/doctype/permlevel - creating
	one via add_permission if it doesn't. Returns (name, created)."""
	setup_custom_perms(doctype)
	filters = {"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0}
	name = frappe.db.get_value("Custom DocPerm", filters, "name")
	if name:
		return name, False
	return add_permission(doctype, role, permlevel), True


def apply_role_permissions(role, doctype, values, permlevel=0):
	"""Fully set a role's permissions on a doctype at the given permlevel.
	Any ptype not in `values` is treated as 0 (so this can also revoke)."""
	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} not found").format(role))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	allowed_ptypes = PTYPES if permlevel == 0 else LEVEL_PTYPES
	values = {ptype: 1 if values.get(ptype) else 0 for ptype in allowed_ptypes}
	name, _created = _ensure_custom_docperm(doctype, role, permlevel)
	update_custom_docperm(name, values)

	validate_permissions_for_doctype(doctype)
	frappe.clear_cache(doctype=doctype)


def apply_bulk_permissions(role, items):
	"""Fully set a role's level-0 permissions on several doctypes at once.
	items: [{"doctype": ..., "permissions": {ptype: 1, ...}}, ...]."""
	for item in items:
		apply_role_permissions(role, item["doctype"], item["permissions"], permlevel=0)
	return len(items)


def update_role_permission(role, doctype, ptype, value, permlevel=0):
	"""Update a single ptype for a role/doctype/permlevel combo, creating the Custom DocPerm
	row first if needed. Used by the Access Checkers' Edit Mode, where each checkbox click saves
	immediately (same UX as Role Permission Manager), instead of batching every ptype like
	apply_role_permissions/apply_bulk_permissions."""
	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} not found").format(role))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))
	if ptype not in PTYPES:
		frappe.throw(_("Invalid permission type {0}").format(ptype))

	allowed_ptypes = PTYPES if permlevel == 0 else LEVEL_PTYPES
	name, created = _ensure_custom_docperm(doctype, role, permlevel)
	if created:
		# add_permission() always grants read and leaves every other ptype at its DocField
		# default (which isn't necessarily 0) - zero everything except what was just asked for,
		# so a brand-new row never silently grants more than the one checkbox that was clicked.
		update_custom_docperm(name, {p: 1 if p == ptype and value else 0 for p in allowed_ptypes})
	else:
		update_custom_docperm(name, {ptype: 1 if value else 0})

	validate_permissions_for_doctype(doctype)
	frappe.clear_cache(doctype=doctype)
