import frappe
from frappe import _

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


def get_user_role_permissions(doctype, user, permlevel=0):
	"""Effective ptype access for `user` on `doctype` at `permlevel`, merged (OR-ed) across every
	role the user has. Document-level only - ignores if_owner and per-document User Permission
	restrictions, since this is a baseline "can the user even use this doctype" check."""
	roles = frappe.get_roles(user)
	perms = {ptype: 0 for ptype in PTYPES}
	for perm in frappe.get_meta(doctype).permissions:
		if perm.role in roles and (perm.permlevel or 0) == permlevel:
			for ptype in PTYPES:
				if perm.get(ptype):
					perms[ptype] = 1
	return perms
