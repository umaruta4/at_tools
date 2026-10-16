import frappe


class MetadataRepository:
	"""Read-only access to DocType metadata and Role records."""

	def get_meta(self, doctype):
		"""Return the meta of ``doctype`` or None when the doctype does not exist."""
		if not doctype:
			return None
		try:
			return frappe.get_meta(doctype)
		except frappe.DoesNotExistError:
			clear_last_message = getattr(frappe, "clear_last_message", None)
			if clear_last_message:
				clear_last_message()
			return None

	def doctype_exists(self, doctype) -> bool:
		return bool(doctype and frappe.db.exists("DocType", doctype))

	def get_role(self, role):
		if not role:
			return None
		return frappe.db.get_value("Role", role, ["name", "disabled"], as_dict=True)
