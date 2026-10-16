import frappe
from frappe import _
from frappe.model.document import Document

from at_tools.permission_dependency_manager.constants import (
	DEPENDENCY_DOCTYPE,
	MANUAL,
	SOURCE_MANUAL,
)


class PermissionDependency(Document):
	"""Configuration/control layer. Enforcement stays with native DocPerm."""

	def validate(self):
		self.validate_self_reference()
		self.validate_unique()
		self.set_manual_defaults()

	def validate_self_reference(self):
		if self.parent_doctype == self.dependency_doctype:
			frappe.throw(_("{0} cannot be a dependency of itself.").format(self.parent_doctype))

	def validate_unique(self):
		duplicate = frappe.db.exists(
			DEPENDENCY_DOCTYPE,
			{
				"role": self.role,
				"parent_doctype": self.parent_doctype,
				"dependency_doctype": self.dependency_doctype,
				"name": ("!=", self.name),
			},
		)
		if duplicate:
			frappe.throw(
				_("Dependency {0} is already configured for role {1} on {2}.").format(
					self.dependency_doctype, self.role, self.parent_doctype
				),
				frappe.DuplicateEntryError,
			)

	def set_manual_defaults(self):
		if self.source_type == SOURCE_MANUAL:
			self.dependency_type = MANUAL
