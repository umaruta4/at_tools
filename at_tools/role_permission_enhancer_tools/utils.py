import frappe
from frappe import _
from frappe.core.doctype.custom_docperm.custom_docperm import update_custom_docperm
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.permissions import add_permission, setup_custom_perms

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


def _check_access():
	frappe.only_for("System Manager")
	if not is_tool_enabled(TOOL):
		frappe.throw(_("{0} is not enabled in AT Tools Settings").format(TOOL))


@frappe.whitelist()
def get_ptypes():
	_check_access()
	return PTYPES


@frappe.whitelist()
def get_role_permissions(doctype):
	"""Effective permissions per role for one DocType (standard + custom)."""
	_check_access()
	return [
		{
			"role": perm.role,
			"permlevel": perm.permlevel,
			**{ptype: perm.get(ptype) or 0 for ptype in PTYPES},
		}
		for perm in frappe.get_meta(doctype).permissions
	]


@frappe.whitelist()
def get_linked_doctypes(doctype):
	"""DocTypes needed to access this doctype: direct Links + Links inside child tables."""
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

	return list(result.values())


@frappe.whitelist()
def set_role_permissions(role, doctype, permissions):
	"""Fully set a role's permissions on a doctype. Any ptype not sent is treated as 0."""
	_check_access()
	_apply(role, doctype, frappe.parse_json(permissions), grant_only=False)


@frappe.whitelist()
def grant_linked_permissions(role, items):
	"""Grant permissions on several related doctypes. Only ever adds, never revokes existing ones."""
	_check_access()
	items = frappe.parse_json(items)
	for item in items:
		_apply(role, item["doctype"], item["permissions"], grant_only=True)
	return len(items)


def _apply(role, doctype, values, grant_only):
	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} not found").format(role))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype))

	values = {ptype: 1 if values.get(ptype) else 0 for ptype in PTYPES if ptype in values or not grant_only}
	if grant_only:
		values = {ptype: value for ptype, value in values.items() if value}
		if not values:
			return

	# Same as Role Permission Manager: copy the standard DocPerm to Custom DocPerm first
	setup_custom_perms(doctype)
	filters = {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}
	if not frappe.db.exists("Custom DocPerm", filters):
		add_permission(doctype, role, 0)

	name = frappe.db.get_value("Custom DocPerm", filters, "name")
	update_custom_docperm(name, values)

	validate_permissions_for_doctype(doctype)
	frappe.clear_cache(doctype=doctype)
