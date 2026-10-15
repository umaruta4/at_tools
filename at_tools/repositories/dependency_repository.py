import frappe

from at_tools.constants import (
	CLASS_MASTER,
	CLASS_TRANSACTION,
	CLASS_UNKNOWN,
	DEFAULT_RECOMMENDATIONS,
	DEPENDENCY_DOCTYPE,
	PERMISSION_TYPES,
	SETTINGS_DOCTYPE,
)

SETTINGS_FIELDS = {
	CLASS_MASTER: "master_permissions",
	CLASS_TRANSACTION: "transaction_permissions",
	CLASS_UNKNOWN: "unknown_permissions",
}


class DependencyRepository:
	"""Persistence of the Permission Dependency configuration layer."""

	def get_for_role(self, role, parent_doctype) -> list:
		return frappe.get_all(
			DEPENDENCY_DOCTYPE,
			filters={"role": role, "parent_doctype": parent_doctype},
			fields=["*"],
			order_by="creation asc",
		)

	def get_name(self, role, parent_doctype, dependency_doctype):
		return frappe.db.get_value(
			DEPENDENCY_DOCTYPE,
			{
				"role": role,
				"parent_doctype": parent_doctype,
				"dependency_doctype": dependency_doctype,
			},
		)

	def upsert(self, values: dict) -> str:
		name = self.get_name(values["role"], values["parent_doctype"], values["dependency_doctype"])
		if name:
			doc = frappe.get_doc(DEPENDENCY_DOCTYPE, name)
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": DEPENDENCY_DOCTYPE, **values})
			doc.insert(ignore_permissions=True)
		return doc.name

	def delete(self, name) -> None:
		frappe.delete_doc(DEPENDENCY_DOCTYPE, name, ignore_permissions=True)

	def get_settings(self) -> dict:
		"""Recommendation settings, falling back to the built-in defaults."""
		recommendations = {key: list(value) for key, value in DEFAULT_RECOMMENDATIONS.items()}
		ignored = []
		try:
			doc = frappe.get_cached_doc(SETTINGS_DOCTYPE)
		except Exception:
			# settings doctype not migrated yet: defaults still work
			doc = None

		if doc:
			for classification, fieldname in SETTINGS_FIELDS.items():
				parsed = self.parse_permission_list(doc.get(fieldname))
				if parsed:
					recommendations[classification] = parsed
			ignored = [line.strip() for line in (doc.get("ignored_doctypes") or "").splitlines()]

		return {
			"recommendations": recommendations,
			"ignored_doctypes": [d for d in ignored if d],
		}

	@staticmethod
	def parse_permission_list(value) -> list:
		"""'Read, Select' -> ['read', 'select'] (unknown names are dropped)."""
		names = [part.strip().lower() for part in (value or "").replace("\n", ",").split(",")]
		return [ptype for ptype in PERMISSION_TYPES if ptype in names]
