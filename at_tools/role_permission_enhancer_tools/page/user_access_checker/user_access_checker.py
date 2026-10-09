import frappe
from frappe import _

from at_tools.role_permission_enhancer_tools.utils import (
	PTYPES,
	check_access,
	find_linked_doctypes,
	find_related_settings,
	get_roles_permissions,
	update_role_permission,
)


@frappe.whitelist()
def get_ptypes():
	check_access()
	return PTYPES


@frappe.whitelist()
def get_roles(user):
	"""Roles behind the merged access this tool reports for `user` (same set frappe.get_roles
	uses), so the caller can offer a single one of them instead of the merged view."""
	check_access()
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} not found").format(user))
	return frappe.get_roles(user)


@frappe.whitelist()
def check_user_access(user, doctype, role=None):
	"""For `user`, compute effective doctype-level access (permlevel 0) to `doctype`, every
	doctype it links to (direct Link + Link inside child tables), and every Settings (Single)
	doctype belonging to a module touched by any of those doctypes - e.g. checking Purchase
	Order also surfaces Buying Settings (same module as Purchase Order) and Stock Settings
	(same module as the linked Item).

	By default this is merged (OR-ed) across every role the user has. Pass `role` to narrow
	it down to just that one role instead - used to show/edit a single role's own permissions
	rather than the user's combined access.

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

	roles = [role] if role else frappe.get_roles(user)

	def row(target, via=None, kind=None):
		return {"doctype": target, "via": via, "kind": kind, **get_roles_permissions(target, roles)}

	linked = find_linked_doctypes(doctype)
	settings = find_related_settings(doctype, linked)

	return {
		"target": row(doctype),
		"linked": [row(item["doctype"], item["via"], item["kind"]) for item in linked],
		"settings": [row(s["name"], s["module"], "Settings") for s in settings],
	}


@frappe.whitelist()
def update_access(role, doctype, ptype, value):
	"""Update a single ptype for `role` on `doctype` (level 0) - called immediately on every
	checkbox click in this page's Edit Mode, same UX as Role Permission Manager."""
	check_access()
	update_role_permission(role, doctype, ptype, frappe.utils.cint(value))
