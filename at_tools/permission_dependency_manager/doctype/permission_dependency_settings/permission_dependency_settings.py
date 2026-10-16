import frappe
from frappe import _
from frappe.model.document import Document

from at_tools.permission_dependency_manager.constants import PERMISSION_TYPES

PERMISSION_FIELDS = ("master_permissions", "transaction_permissions", "unknown_permissions")


class PermissionDependencySettings(Document):
	def validate(self):
		for fieldname in PERMISSION_FIELDS:
			names = [part.strip().lower() for part in (self.get(fieldname) or "").split(",")]
			invalid = [name for name in names if name and name not in PERMISSION_TYPES]
			if invalid:
				frappe.throw(
					_("Invalid permission type in {0}: {1}").format(
						self.meta.get_label(fieldname), ", ".join(invalid)
					)
				)
