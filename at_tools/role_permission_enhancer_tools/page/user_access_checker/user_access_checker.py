import frappe
from frappe import _

from at_tools.role_permission_enhancer_tools.utils import (
	PTYPES,
	check_access,
	find_linked_doctypes,
	find_related_settings,
	get_user_role_permissions,
)


@frappe.whitelist()
def get_ptypes():
	check_access()
	return PTYPES


@frappe.whitelist()
def check_user_access(user, doctype):
	"""For `user`, compute effective doctype-level access (permlevel 0, merged across every
	role the user has) to `doctype`, every doctype it links to (direct Link + Link inside
	child tables), and every Settings (Single) doctype belonging to a module touched by any
	of those doctypes - e.g. checking Purchase Order also surfaces Buying Settings (same
	module as Purchase Order) and Stock Settings (same module as the linked Item).

	This is a baseline "can the user even use this doctype" check: it ignores if_owner and
	per-document User Permission restrictions, which only matter once the user already has
	doctype-level access. Meant to catch missing access before a dry run, not to fully
	simulate permission checks.
	"""
	check_access()
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} not found").format(user))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	def row(target, via=None, kind=None):
		return {"doctype": target, "via": via, "kind": kind, **get_user_role_permissions(target, user)}

	linked = find_linked_doctypes(doctype)
	settings = find_related_settings(doctype, linked)

	return {
		"target": row(doctype),
		"linked": [row(item["doctype"], item["via"], item["kind"]) for item in linked],
		"settings": [row(s["name"], s["module"], "Settings") for s in settings],
	}
