import frappe
from frappe import _
from frappe.model.document import Document


class UserPermissionTemplateItem(Document):
	def validate(self):
		if self.value_source == "Fixed Value" and not self.fixed_value:
			frappe.throw(_("Row {0}: For Value is required for Fixed Value").format(self.idx))

		if self.value_source == "Employee Field":
			if not self.employee_field:
				frappe.throw(_("Row {0}: Employee Field is required").format(self.idx))

			# "name" is not a metadata field, but it's valid as the Employee ID
			if self.employee_field == "name":
				if self.allow != "Employee":
					frappe.throw(_("Row {0}: Employee Field 'name' can only be used with Allow = Employee").format(self.idx))
			elif not frappe.get_meta("Employee").has_field(self.employee_field):
				frappe.throw(_("Row {0}: Field {1} does not exist on Employee").format(self.idx, frappe.bold(self.employee_field)))
