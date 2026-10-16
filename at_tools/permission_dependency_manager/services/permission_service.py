import frappe
from frappe import _

from at_tools.permission_dependency_manager.constants import (
	ADMIN_ROLE,
	AUTOMATIC_ROLES,
	NOT_ALLOWED_DOCTYPES,
	PERMISSION_TYPES,
	SUBMIT_PERMISSION_TYPES,
)


class PermissionService:
	"""Reads native role permissions and grants additional ones (additive only)."""

	def __init__(self, repository=None, metadata_repository=None):
		self._repository = repository
		self._metadata_repository = metadata_repository

	@property
	def repository(self):
		if self._repository is None:
			from at_tools.permission_dependency_manager.repositories.permission_repository import (
				PermissionRepository,
			)

			self._repository = PermissionRepository()
		return self._repository

	@property
	def metadata_repository(self):
		if self._metadata_repository is None:
			from at_tools.permission_dependency_manager.repositories.metadata_repository import (
				MetadataRepository,
			)

			self._metadata_repository = MetadataRepository()
		return self._metadata_repository

	# ------------------------------------------------------------------ helpers

	@staticmethod
	def empty_flags() -> dict:
		return {ptype: 0 for ptype in PERMISSION_TYPES}

	@staticmethod
	def normalize_permissions(permissions) -> dict:
		"""Accept ['read', 'select'] or {'read': 1} and return a full flag dict."""
		flags = PermissionService.empty_flags()
		if permissions is None:
			return flags

		if isinstance(permissions, dict):
			requested = [key for key, value in permissions.items() if PermissionService.as_int(value)]
			unknown = [key for key in permissions if key not in PERMISSION_TYPES]
		elif isinstance(permissions, (list, tuple, set)):
			requested = list(permissions)
			unknown = [key for key in requested if key not in PERMISSION_TYPES]
		else:
			frappe.throw(_("Permissions must be a list or a dict."), frappe.ValidationError)

		if unknown:
			frappe.throw(
				_("Invalid permission type: {0}").format(", ".join(str(key) for key in unknown)),
				frappe.ValidationError,
			)

		for ptype in requested:
			flags[ptype] = 1
		return flags

	@staticmethod
	def as_int(value) -> int:
		if isinstance(value, str):
			value = value.strip().lower()
			return int(value not in ("", "0", "false", "no", "null", "none"))
		return int(bool(value))

	# --------------------------------------------------------------- validation

	def validate_role(self, role) -> None:
		record = self.metadata_repository.get_role(role)
		if not record:
			frappe.throw(_("Role {0} does not exist.").format(role), frappe.ValidationError)
		if self.as_int(record.get("disabled")):
			frappe.throw(_("Role {0} is disabled.").format(role), frappe.ValidationError)
		if role == ADMIN_ROLE or (role in AUTOMATIC_ROLES and frappe.session.user != ADMIN_ROLE):
			frappe.throw(
				_("Permissions of role {0} cannot be managed here.").format(role),
				frappe.PermissionError,
			)

	def validate_doctype(self, doctype):
		"""Doctype must exist, must not be a child table and must be manageable."""
		meta = self.metadata_repository.get_meta(doctype)
		if not meta:
			frappe.throw(_("DocType {0} does not exist.").format(doctype), frappe.ValidationError)
		if doctype in NOT_ALLOWED_DOCTYPES:
			frappe.throw(
				_("Permissions of DocType {0} cannot be managed here.").format(doctype),
				frappe.PermissionError,
			)
		if self.as_int(getattr(meta, "istable", 0)):
			frappe.throw(
				_("{0} is a child table and has no permissions of its own.").format(doctype),
				frappe.ValidationError,
			)
		return meta

	def validate_flags(self, doctype, flags, meta=None) -> None:
		"""Mirror the native DocPerm rules so we fail early with a clear message."""
		meta = meta or self.validate_doctype(doctype)
		submit_like = [ptype for ptype in SUBMIT_PERMISSION_TYPES if flags.get(ptype)]

		if submit_like and not self.as_int(getattr(meta, "is_submittable", 0)):
			frappe.throw(
				_("{0} is not submittable: cannot set {1}.").format(doctype, ", ".join(submit_like)),
				frappe.ValidationError,
			)
		if submit_like and not flags.get("write"):
			frappe.throw(
				_("{0}: cannot set Submit, Cancel or Amend without Write.").format(doctype),
				frappe.ValidationError,
			)
		if flags.get("cancel") and not flags.get("submit"):
			frappe.throw(
				_("{0}: cannot set Cancel without Submit.").format(doctype), frappe.ValidationError
			)

	# -------------------------------------------------------------------- reads

	def get_current_permissions(self, role, doctype) -> dict:
		"""Level 0 permissions the role has today (OR over its rules)."""
		flags = self.empty_flags()
		for rule in self.repository.get_role_rules(doctype, role):
			for ptype in PERMISSION_TYPES:
				if self.as_int(rule.get(ptype)):
					flags[ptype] = 1
		return flags

	# ------------------------------------------------------------------- writes

	def grant(self, role, doctype, permissions) -> dict:
		"""Additively grant ``permissions`` on ``doctype`` to ``role``.

		Existing permissions are never removed or lowered, and no second rule is
		created when the role already has a level 0 rule on the doctype.
		"""
		requested = self.normalize_permissions(permissions)
		meta = self.validate_doctype(doctype)
		result = {"doctype": doctype, "added": [], "created_rule": 0}

		if not any(requested.values()):
			return result

		self.repository.ensure_custom_perms(doctype)
		rule = self.repository.get_custom_rule(doctype, role)

		existing = self.empty_flags()
		if rule:
			existing = {ptype: self.as_int(rule.get(ptype)) for ptype in PERMISSION_TYPES}

		to_add = [ptype for ptype in PERMISSION_TYPES if requested[ptype] and not existing[ptype]]
		if not to_add:
			return result

		effective = {ptype: int(existing[ptype] or requested[ptype]) for ptype in PERMISSION_TYPES}
		self.validate_flags(doctype, effective, meta=meta)

		if rule:
			self.repository.add_flags(rule.get("name"), to_add)
		else:
			self.repository.insert_rule(doctype, role, requested)
			result["created_rule"] = 1

		self.repository.validate_doctype_permissions(doctype)
		self.repository.clear_cache(doctype)
		result["added"] = to_add
		return result
