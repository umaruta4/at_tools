import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TAB_FIELDNAME = "user_permission_tab"
OWN_FIELDNAMES = {
	TAB_FIELDNAME,
	"user_permission_template",
	"user_permission_items",
	"user_permission_applied",
}


def install():
	"""Called from AT Tools Settings when User Permission Tools is enabled on this site."""
	create_custom_fields(
		{
			"Employee": [
				{
					# New tab at the end of the Employee form. Must come after the last field, so other fields don't shift into this tab
					"fieldname": TAB_FIELDNAME,
					"fieldtype": "Tab Break",
					"label": "User Permission",
					"insert_after": _last_employee_fieldname(),
				},
				{
					"fieldname": "user_permission_template",
					"fieldtype": "Link",
					"label": "User Permission Template",
					"options": "User Permission Template",
					"insert_after": TAB_FIELDNAME,
				},
				{
					"fieldname": "user_permission_items",
					"fieldtype": "Table",
					"label": "User Permissions",
					"options": "User Permission Template Item",
					"insert_after": "user_permission_template",
				},
				{
					# List of User Permission names created by this tool, so manually-created UPs are left untouched
					"fieldname": "user_permission_applied",
					"fieldtype": "Small Text",
					"label": "Applied User Permissions",
					"hidden": 1,
					"read_only": 1,
					"insert_after": "user_permission_items",
				},
			]
		},
		update=True,
	)


def _last_employee_fieldname():
	"""Last Employee field, excluding fields owned by this tool."""
	fieldnames = [f.fieldname for f in frappe.get_meta("Employee").fields if f.fieldname not in OWN_FIELDNAMES]
	return fieldnames[-1]
