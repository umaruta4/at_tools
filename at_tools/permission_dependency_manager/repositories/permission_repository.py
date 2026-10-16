import frappe

from at_tools.permission_dependency_manager.constants import PERMISSION_TYPES

CUSTOM_DOCPERM = "Custom DocPerm"
DOCPERM = "DocPerm"


class PermissionRepository:
	"""All reads/writes against the native DocPerm / Custom DocPerm tables."""

	def has_custom_perms(self, doctype) -> bool:
		return bool(frappe.db.exists(CUSTOM_DOCPERM, {"parent": doctype}))

	def get_role_rules(self, doctype, role) -> list:
		"""Effective level 0 rules of a role (Custom DocPerm wins over DocPerm, like core)."""
		table = CUSTOM_DOCPERM if self.has_custom_perms(doctype) else DOCPERM
		return frappe.get_all(
			table,
			filters={"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
			fields=["*"],
		)

	def ensure_custom_perms(self, doctype):
		"""Copy the standard DocPerm rows to Custom DocPerm once (native behaviour)."""
		from frappe.permissions import setup_custom_perms

		return setup_custom_perms(doctype)

	def get_custom_rule(self, doctype, role):
		rules = frappe.get_all(
			CUSTOM_DOCPERM,
			filters={"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
			fields=["*"],
			order_by="creation asc",
			limit=1,
		)
		return rules[0] if rules else None

	def insert_rule(self, doctype, role, flags: dict) -> str:
		values = {ptype: 1 for ptype in PERMISSION_TYPES if flags.get(ptype)}
		doc = frappe.get_doc(
			{
				"doctype": CUSTOM_DOCPERM,
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
				"if_owner": 0,
				**values,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def add_flags(self, name, ptypes) -> None:
		"""Turn the given permission types on. Never turns anything off."""
		doc = frappe.get_doc(CUSTOM_DOCPERM, name)
		doc.update({ptype: 1 for ptype in ptypes})
		doc.save(ignore_permissions=True)

	def validate_doctype_permissions(self, doctype) -> None:
		from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

		validate_permissions_for_doctype(doctype)

	def clear_cache(self, doctype) -> None:
		frappe.clear_cache(doctype=doctype)

	def savepoint(self, name) -> None:
		frappe.db.savepoint(name)

	def rollback(self, name) -> None:
		frappe.db.rollback(save_point=name)
