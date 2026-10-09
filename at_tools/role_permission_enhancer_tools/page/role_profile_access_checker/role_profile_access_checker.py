import frappe
from frappe import _

from at_tools.role_permission_enhancer_tools.utils import (
	PTYPES,
	check_access,
	find_linked_doctypes,
	find_related_settings,
	get_role_profile_roles,
	get_roles_accessible_doctypes,
	get_roles_permissions,
	update_role_permission,
)


@frappe.whitelist()
def get_ptypes():
	check_access()
	return PTYPES


@frappe.whitelist()
def get_roles(role_profile):
	"""Roles behind the merged access this tool reports for `role_profile`, so the caller can
	offer a single one of them instead of the merged view."""
	check_access()
	if not frappe.db.exists("Role Profile", role_profile):
		frappe.throw(_("Role Profile {0} not found").format(role_profile))
	return get_role_profile_roles(role_profile)


@frappe.whitelist()
def check_role_profile_access(role_profile, doctype=None, role=None):
	"""For `role_profile`, either:

	- no `doctype`: every DocType the profile's roles can at least Read (overview of what this
	  Role Profile can access at all).
	- `doctype` given: the same target/linked-doctypes/related-settings breakdown as
	  user_access_checker.check_user_access.

	By default both are merged (OR-ed) across the profile's roles. Pass `role` (must belong to
	the profile) to narrow either one down to just that single role instead - used to show/edit
	one role's own permissions rather than the profile's combined access.
	"""
	check_access()
	if not frappe.db.exists("Role Profile", role_profile):
		frappe.throw(_("Role Profile {0} not found").format(role_profile))

	roles = get_role_profile_roles(role_profile)
	if role:
		if role not in roles:
			frappe.throw(_("Role {0} is not part of Role Profile {1}").format(role, role_profile))
		roles = [role]

	if not doctype:
		return {"accessible_doctypes": get_roles_accessible_doctypes(roles)}

	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

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
	checkbox click in this page's Edit Mode (overview or detail), same UX as Role Permission
	Manager."""
	check_access()
	update_role_permission(role, doctype, ptype, frappe.utils.cint(value))
