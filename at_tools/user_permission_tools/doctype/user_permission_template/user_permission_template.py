import frappe
from frappe import _
from frappe.model.document import Document


class UserPermissionTemplate(Document):
	def validate(self):
		seen = set()
		for row in self.items:
			key = (row.allow, row.applicable_for, row.value_source, row.fixed_value, row.employee_field)
			if key in seen:
				frappe.throw(_("Row {0}: Duplicate permission row").format(row.idx))
			seen.add(key)
