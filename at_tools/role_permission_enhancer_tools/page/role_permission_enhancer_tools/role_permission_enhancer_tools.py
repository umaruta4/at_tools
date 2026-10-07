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


def _check_access():
	frappe.only_for("System Manager")
	if not is_tool_enabled(TOOL):
		frappe.throw(_("{0} is not enabled in AT Tools Settings").format(TOOL))


@frappe.whitelist()
def get_ptypes():
	_check_access()
	return PTYPES


@frappe.whitelist()
def get_role_permissions(doctype=None, role=None):
	"""Effective permissions (standard + custom), filterable by DocType, Role, or both.

	Mirrors frappe.core.page.permission_manager: when a role is given, permissions are
	looked up across all DocTypes for that role (then narrowed to doctype if also given).
	When only a doctype is given, permissions are looked up for every role on it.
	"""
	_check_access()

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
	_check_access()
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

	items = list(result.values())
	if role:
		for item in items:
			item["permissions"] = _get_level0_permissions(item["doctype"], role)

	return items


def _get_level0_permissions(doctype, role):
	"""A role with no permission row yet on this doctype comes back as all-zero;
	applying any checked ptype later creates the row (see _apply)."""
	for perm in frappe.get_meta(doctype).permissions:
		if perm.role == role and (perm.permlevel or 0) == 0:
			return {ptype: perm.get(ptype) or 0 for ptype in PTYPES}
	return {ptype: 0 for ptype in PTYPES}


@frappe.whitelist()
def set_role_permissions(role, doctype, permissions, permlevel=0):
	"""Fully set a role's permissions on a doctype at the given permlevel. Any ptype not sent is treated as 0."""
	_check_access()
	_apply(role, doctype, frappe.parse_json(permissions), grant_only=False, permlevel=frappe.utils.cint(permlevel))


@frappe.whitelist()
def set_linked_permissions(role, items):
	"""Fully set a role's level-0 permissions on several related doctypes at once.
	Any ptype not sent for a given doctype is treated as 0 (can revoke), same as set_role_permissions."""
	_check_access()
	items = frappe.parse_json(items)
	for item in items:
		_apply(role, item["doctype"], item["permissions"], grant_only=False, permlevel=0)
	return len(items)


def _apply(role, doctype, values, grant_only, permlevel=0):
	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} not found").format(role))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	allowed_ptypes = PTYPES if permlevel == 0 else LEVEL_PTYPES
	values = {ptype: 1 if values.get(ptype) else 0 for ptype in allowed_ptypes if ptype in values or not grant_only}
	if grant_only:
		values = {ptype: value for ptype, value in values.items() if value}
		if not values:
			return

	# Same as Role Permission Manager: copy the standard DocPerm to Custom DocPerm first
	setup_custom_perms(doctype)
	filters = {"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0}
	if not frappe.db.exists("Custom DocPerm", filters):
		add_permission(doctype, role, permlevel)

	name = frappe.db.get_value("Custom DocPerm", filters, "name")
	update_custom_docperm(name, values)

	validate_permissions_for_doctype(doctype)
	frappe.clear_cache(doctype=doctype)
