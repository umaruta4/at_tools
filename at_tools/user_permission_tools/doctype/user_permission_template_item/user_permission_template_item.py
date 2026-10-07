import frappe
from frappe import _
from frappe.model.document import Document


class UserPermissionTemplateItem(Document):
	def validate(self):
		if self.value_source == "Fixed Value" and not self.fixed_value:
			frappe.throw(_("Row {0}: For Value wajib diisi untuk Fixed Value").format(self.idx))

		if self.value_source == "Employee Field":
			if not self.employee_field:
				frappe.throw(_("Row {0}: Employee Field wajib diisi").format(self.idx))

			# "name" bukan field metadata, tapi valid sebagai ID Employee
			if self.employee_field == "name":
				if self.allow != "Employee":
					frappe.throw(_("Row {0}: Employee Field 'name' hanya bisa dipakai dengan Allow = Employee").format(self.idx))
			elif not frappe.get_meta("Employee").has_field(self.employee_field):
				frappe.throw(_("Row {0}: Field {1} tidak ada di Employee").format(self.idx, frappe.bold(self.employee_field)))
