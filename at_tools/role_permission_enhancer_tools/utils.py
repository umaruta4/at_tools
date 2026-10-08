import frappe
from frappe import _
from frappe.permissions import get_all_perms

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


def get_user_role_permissions(doctype, user, permlevel=0):
	"""Effective ptype access for `user` on `doctype` at `permlevel`, merged (OR-ed) across every
	role the user has. Document-level only - ignores if_owner and per-document User Permission
	restrictions, since this is a baseline "can the user even use this doctype" check."""
	return get_roles_permissions(doctype, frappe.get_roles(user), permlevel)


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
