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
	"""Dipanggil dari AT Tools Settings saat User Permission Tools diaktifkan di site ini."""
	create_custom_fields(
		{
			"Employee": [
				{
					# Tab baru di akhir form Employee. Harus setelah field terakhir, supaya field lain tidak ikut pindah tab
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
					# Daftar name User Permission yang dibuat oleh tool ini, supaya UP manual tidak ikut tersentuh
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
	"""Field terakhir Employee selain field milik tool ini."""
	fieldnames = [f.fieldname for f in frappe.get_meta("Employee").fields if f.fieldname not in OWN_FIELDNAMES]
	return fieldnames[-1]
