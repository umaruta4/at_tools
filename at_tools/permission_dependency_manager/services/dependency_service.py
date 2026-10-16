import frappe
from frappe import _

from at_tools.permission_dependency_manager.constants import (
	CHILD_TABLE_LINK,
	CLASS_MASTER,
	CLASS_TRANSACTION,
	CLASS_UNKNOWN,
	DEFAULT_RECOMMENDATIONS,
	FIELD_PREFIX,
	MANUAL,
	PERMISSION_TYPES,
	SAVEPOINT,
	SOURCE_DETECTED,
	SOURCE_MANUAL,
	STATUS_DISABLED,
	STATUS_MISSING,
	STATUS_PARTIAL,
	STATUS_SATISFIED,
)
from at_tools.permission_dependency_manager.services.permission_service import PermissionService


class PermissionDependencyService:
	"""Combines detected dependencies, saved configuration and native permissions."""

	def __init__(
		self,
		analyzer=None,
		repository=None,
		permission_service=None,
		metadata_repository=None,
	):
		self._analyzer = analyzer
		self._repository = repository
		self._permission_service = permission_service
		self._metadata_repository = metadata_repository

	# ------------------------------------------------------- lazy collaborators

	@property
	def metadata_repository(self):
		if self._metadata_repository is None:
			from at_tools.permission_dependency_manager.repositories.metadata_repository import (
				MetadataRepository,
			)

			self._metadata_repository = MetadataRepository()
		return self._metadata_repository

	@property
	def analyzer(self):
		if self._analyzer is None:
			from at_tools.permission_dependency_manager.services.metadata_service import DependencyAnalyzer

			self._analyzer = DependencyAnalyzer(self.metadata_repository)
		return self._analyzer

	@property
	def repository(self):
		if self._repository is None:
			from at_tools.permission_dependency_manager.repositories.dependency_repository import (
				DependencyRepository,
			)

			self._repository = DependencyRepository()
		return self._repository

	@property
	def permission_service(self):
		if self._permission_service is None:
			self._permission_service = PermissionService(metadata_repository=self.metadata_repository)
		return self._permission_service

	# -------------------------------------------------------------------- reads

	def get_dependencies(self, role, doctype) -> dict:
		self.validate_context(role, doctype)
		settings = self.repository.get_settings()

		detected = self.analyzer.analyze(doctype, ignored=settings.get("ignored_doctypes"))
		configured = self.repository.get_for_role(role, doctype)
		rows = self.merge(detected, configured)

		for row in rows:
			classification, recommended = self.recommend(row["doctype"], settings)
			row["classification"] = classification
			row["recommended_permissions"] = recommended
			row["current_permissions"] = self.permission_service.get_current_permissions(
				role, row["doctype"]
			)
			if not row["configured"]:
				row["permissions"] = dict(recommended)
			row["status"] = self.calculate_status(row)
			row["missing_permissions"] = self.get_missing(row)

		return {
			"role": role,
			"parent_doctype": doctype,
			"permission_types": list(PERMISSION_TYPES),
			"dependencies": rows,
		}

	def get_existing_permissions(self, role, doctypes) -> dict:
		"""Current native permissions of ``role`` for each doctype in ``doctypes``."""
		self.permission_service.validate_role(role)
		if isinstance(doctypes, str):
			doctypes = [doctypes]
		if not isinstance(doctypes, (list, tuple)):
			frappe.throw(_("Doctypes must be a list."), frappe.ValidationError)

		out = {}
		for doctype in doctypes:
			self.permission_service.validate_doctype(doctype)
			out[doctype] = self.permission_service.get_current_permissions(role, doctype)
		return out

	def recommend(self, dependency_doctype, settings=None) -> tuple:
		"""Return (classification, recommended permission flags). Never applied by itself."""
		recommendations = (settings or {}).get("recommendations") or DEFAULT_RECOMMENDATIONS
		meta = self.metadata_repository.get_meta(dependency_doctype)

		if not meta:
			classification = CLASS_UNKNOWN
		elif PermissionService.as_int(getattr(meta, "is_submittable", 0)):
			classification = CLASS_TRANSACTION
		else:
			classification = CLASS_MASTER

		ptypes = list(recommendations.get(classification) or DEFAULT_RECOMMENDATIONS[classification])
		if meta and PermissionService.as_int(getattr(meta, "issingle", 0)):
			# a Single has no list to pick from
			ptypes = [ptype for ptype in ptypes if ptype != "select"]

		return classification, PermissionService.normalize_permissions(ptypes)

	# ------------------------------------------------------------------- merges

	@staticmethod
	def merge(detected, configured) -> list:
		"""Detected dependencies first (in field order), then configured-only rows."""
		rows = {}

		for dependency in detected:
			data = dependency.as_dict()
			rows[dependency.doctype] = {
				"name": None,
				"doctype": dependency.doctype,
				"source": {
					"doctype": data["source_doctype"],
					"fieldname": data["source_field"],
				},
				"sources": data["sources"],
				"source_type": SOURCE_DETECTED,
				"dependency_type": data["dependency_type"],
				"reqd": data["reqd"],
				"configured": 0,
				# Detected != Granted: only mandatory links are pre-selected
				"enabled": data["reqd"],
				"permissions": PermissionService.empty_flags(),
				"reason": "",
				"explanation": PermissionDependencyService.explain(dependency.doctype, data["sources"]),
			}

		for record in configured:
			dependency_doctype = record.get("dependency_doctype")
			flags = PermissionDependencyService.flags_from_record(record)
			row = rows.get(dependency_doctype)

			if row is None:
				row = {
					"doctype": dependency_doctype,
					"source": {
						"doctype": record.get("source_doctype"),
						"fieldname": record.get("source_field"),
					},
					"sources": [],
					"source_type": SOURCE_MANUAL,
					"dependency_type": MANUAL,
					"reqd": 0,
					"explanation": record.get("reason") or "",
				}
				rows[dependency_doctype] = row

			row.update(
				{
					"name": record.get("name"),
					"configured": 1,
					"enabled": PermissionService.as_int(record.get("enabled")),
					"permissions": flags,
					"reason": record.get("reason") or "",
				}
			)

		return list(rows.values())

	@staticmethod
	def flags_from_record(record) -> dict:
		return {
			ptype: PermissionService.as_int(record.get(FIELD_PREFIX + ptype)) for ptype in PERMISSION_TYPES
		}

	@staticmethod
	def explain(dependency_doctype, sources) -> str:
		lines = []
		for source in sources:
			if source["dependency_type"] == CHILD_TABLE_LINK:
				template = "{0} is referenced by the {1} child table through the {2} Link field."
			else:
				template = "{0} is referenced by {1} through the {2} Link field."
			lines.append(template.format(dependency_doctype, source["doctype"], source["fieldname"]))
		return "\n".join(lines)

	@staticmethod
	def calculate_status(row) -> str:
		if row.get("configured") and not row.get("enabled"):
			return STATUS_DISABLED

		required = [ptype for ptype in PERMISSION_TYPES if row["permissions"].get(ptype)]
		granted = [ptype for ptype in required if row["current_permissions"].get(ptype)]

		if len(granted) == len(required):
			return STATUS_SATISFIED
		if not granted:
			return STATUS_MISSING
		return STATUS_PARTIAL

	@staticmethod
	def get_missing(row) -> list:
		return [
			ptype
			for ptype in PERMISSION_TYPES
			if row["permissions"].get(ptype) and not row["current_permissions"].get(ptype)
		]

	# ------------------------------------------------------------------- writes

	def save_configuration(self, role, doctype, rows) -> dict:
		"""Persist the dependency configuration. Does not touch native permissions."""
		self.validate_context(role, doctype)
		if not isinstance(rows, (list, tuple)):
			frappe.throw(_("Dependencies must be a list."), frappe.ValidationError)

		settings = self.repository.get_settings()
		detected = {
			dependency.doctype: dependency.as_dict()
			for dependency in self.analyzer.analyze(doctype, ignored=settings.get("ignored_doctypes"))
		}
		existing = {
			record.get("dependency_doctype") for record in self.repository.get_for_role(role, doctype)
		}

		seen = set()
		saved = []
		for row in rows:
			if not isinstance(row, dict):
				frappe.throw(_("Invalid dependency payload."), frappe.ValidationError)

			dependency_doctype = row.get("dependency_doctype")
			if dependency_doctype in seen:
				frappe.throw(
					_("Duplicate dependency {0}.").format(dependency_doctype), frappe.ValidationError
				)
			seen.add(dependency_doctype)

			meta = self.validate_dependency_doctype(dependency_doctype, doctype)
			flags = PermissionService.normalize_permissions(row.get("permissions"))
			enabled = PermissionService.as_int(row.get("enabled"))
			source = detected.get(dependency_doctype)  # never trust source info from the client

			if not enabled and source and dependency_doctype not in existing:
				continue  # untouched recommendation: nothing to remember

			if enabled:
				if not any(flags.values()):
					frappe.throw(
						_("Select at least one permission for {0}.").format(dependency_doctype),
						frappe.ValidationError,
					)
				self.permission_service.validate_flags(dependency_doctype, flags, meta=meta)

			values = {
				"role": role,
				"parent_doctype": doctype,
				"dependency_doctype": dependency_doctype,
				"source_type": SOURCE_DETECTED if source else SOURCE_MANUAL,
				"source_doctype": source["source_doctype"] if source else None,
				"source_field": source["source_field"] if source else None,
				"dependency_type": source["dependency_type"] if source else MANUAL,
				"reason": (row.get("reason") or "").strip(),
				"enabled": enabled,
			}
			values.update({FIELD_PREFIX + ptype: flags[ptype] for ptype in PERMISSION_TYPES})
			saved.append(self.repository.upsert(values))

		return {"saved": saved}

	def remove_dependency(self, role, doctype, dependency_doctype) -> dict:
		"""Forget a configuration row. Native permissions are left untouched."""
		self.validate_context(role, doctype)
		name = self.repository.get_name(role, doctype, dependency_doctype)
		if not name:
			frappe.throw(
				_("No dependency configuration found for {0}.").format(dependency_doctype),
				frappe.ValidationError,
			)
		self.repository.delete(name)
		return {"removed": name}

	def apply_dependencies(self, role, doctype) -> dict:
		"""Grant every enabled, saved dependency. All or nothing."""
		self.validate_context(role, doctype)
		records = [
			record
			for record in self.repository.get_for_role(role, doctype)
			if PermissionService.as_int(record.get("enabled"))
		]

		permission_repository = self.permission_service.repository
		permission_repository.savepoint(SAVEPOINT)
		results = []
		try:
			for record in records:
				dependency_doctype = record.get("dependency_doctype")
				self.validate_dependency_doctype(dependency_doctype, doctype)
				results.append(
					self.permission_service.grant(role, dependency_doctype, self.flags_from_record(record))
				)
		except Exception:
			permission_repository.rollback(SAVEPOINT)
			raise

		return {
			"role": role,
			"parent_doctype": doctype,
			"applied": results,
			"changed": [result["doctype"] for result in results if result["added"]],
		}

	# --------------------------------------------------------------- validation

	def validate_context(self, role, doctype) -> None:
		self.permission_service.validate_role(role)
		self.permission_service.validate_doctype(doctype)

	def validate_dependency_doctype(self, dependency_doctype, parent_doctype):
		if not dependency_doctype or not isinstance(dependency_doctype, str):
			frappe.throw(_("Dependency DocType is required."), frappe.ValidationError)
		if dependency_doctype == parent_doctype:
			frappe.throw(
				_("{0} cannot be a dependency of itself.").format(parent_doctype), frappe.ValidationError
			)
		return self.permission_service.validate_doctype(dependency_doctype)
