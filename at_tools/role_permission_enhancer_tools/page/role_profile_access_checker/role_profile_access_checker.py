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
)


@frappe.whitelist()
def get_ptypes():
	check_access()
	return PTYPES


@frappe.whitelist()
def check_role_profile_access(role_profile, doctype=None):
	"""For `role_profile`, either:

	- no `doctype`: every DocType the profile's roles can at least Read (overview of what this
	  Role Profile can access at all).
	- `doctype` given: the same target/linked-doctypes/related-settings breakdown as
	  user_access_checker.check_user_access, merged (OR-ed) across the profile's roles instead
	  of a single user's roles.
	"""
	check_access()
	if not frappe.db.exists("Role Profile", role_profile):
		frappe.throw(_("Role Profile {0} not found").format(role_profile))

	roles = get_role_profile_roles(role_profile)

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
