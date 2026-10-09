import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.permissions import add_permission, get_all_perms, setup_custom_perms

from at_tools.role_permission_enhancer_tools.utils import (
	PTYPES,
	apply_bulk_permissions,
	apply_role_permissions,
	check_access,
	find_linked_doctypes,
)


@frappe.whitelist()
def get_ptypes():
	check_access()
	return PTYPES


@frappe.whitelist()
def get_role_permissions(doctype=None, role=None):
	"""Effective permissions (standard + custom), filterable by DocType, Role, or both.

	Mirrors frappe.core.page.permission_manager: when a role is given, permissions are
	looked up across all DocTypes for that role (then narrowed to doctype if also given).
	When only a doctype is given, permissions are looked up for every role on it.
	"""
	check_access()

	if role:
		perms = get_all_perms(role)
		if doctype:
			perms = [p for p in perms if p.parent == doctype]
		return [
			{
				"doctype": perm.parent,
				"role": perm.role,
				"permlevel": perm.permlevel,
				**{ptype: perm.get(ptype) or 0 for ptype in PTYPES},
			}
			for perm in perms
		]

	if not doctype:
		return []

	return [
		{
			"doctype": doctype,
			"role": perm.role,
			"permlevel": perm.permlevel,
			**{ptype: perm.get(ptype) or 0 for ptype in PTYPES},
		}
		for perm in frappe.get_meta(doctype).permissions
	]


@frappe.whitelist()
def get_linked_doctypes(doctype, role=None):
	"""DocTypes needed to access this doctype: direct Links + Links inside child tables.

	When `role` is given, each item also carries that role's current level-0 permissions
	on the linked doctype, so the caller can show (and edit) the actual current state.
	"""
	check_access()
	items = find_linked_doctypes(doctype)
	if role:
		for item in items:
			item["permissions"] = _get_level0_permissions(item["doctype"], role)

	return items


def _get_level0_permissions(doctype, role):
	"""A role with no permission row yet on this doctype comes back as all-zero;
	applying any checked ptype later creates the row (see apply_role_permissions)."""
	for perm in frappe.get_meta(doctype).permissions:
		if perm.role == role and (perm.permlevel or 0) == 0:
			return {ptype: perm.get(ptype) or 0 for ptype in PTYPES}
	return {ptype: 0 for ptype in PTYPES}


@frappe.whitelist()
def add_role_permission_rule(doctype, role, permlevel=0):
	"""Add a new permission rule (defaults to read=1) for a role on a doctype at the given level.

	Mirrors frappe.core.page.permission_manager.add. Lets a role/doctype/permlevel combination
	that has no row yet show up in the table, where it can then be adjusted via Set.
	"""
	check_access()
	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} not found").format(role))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	add_permission(doctype, role, frappe.utils.cint(permlevel))


@frappe.whitelist()
def set_role_permissions(role, doctype, permissions, permlevel=0):
	"""Fully set a role's permissions on a doctype at the given permlevel. Any ptype not sent is treated as 0."""
	check_access()
	apply_role_permissions(role, doctype, frappe.parse_json(permissions), permlevel=frappe.utils.cint(permlevel))


@frappe.whitelist()
def set_linked_permissions(role, items):
	"""Fully set a role's level-0 permissions on several related doctypes at once.
	Any ptype not sent for a given doctype is treated as 0 (can revoke), same as set_role_permissions."""
	check_access()
	return apply_bulk_permissions(role, frappe.parse_json(items))


@frappe.whitelist()
def remove_role_permission_rule(doctype, role, permlevel=0):
	"""Remove a role's permission rule on a doctype at the given level.

	Mirrors frappe.core.page.permission_manager.remove (if_owner is always 0 here, since this
	tool doesn't expose the "Only If Creator" option).
	"""
	check_access()
	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} not found").format(role))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	permlevel = frappe.utils.cint(permlevel)
	setup_custom_perms(doctype)

	for name in frappe.get_all(
		"Custom DocPerm",
		filters={"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0},
		pluck="name",
	):
		frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)

	if not frappe.get_all("Custom DocPerm", {"parent": doctype}):
		frappe.throw(_("There must be at least one permission rule."), title=_("Cannot Remove"))

	validate_permissions_for_doctype(doctype, for_remove=True, alert=True)
