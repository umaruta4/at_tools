from at_tools.constants import (
	CHILD_TABLE_LINK,
	DIRECT_LINK,
	TABLE_FIELDTYPES,
)
from at_tools.dto import DependencySource, DetectedDependency


class DependencyAnalyzer:
	"""Detects permission dependencies of a doctype from its metadata.

	Scope (MVP): Link fields of the doctype itself and Link fields of its child
	tables. There is no recursive traversal into the linked doctypes.
	"""

	def __init__(self, metadata_repository=None):
		self._metadata_repository = metadata_repository

	@property
	def metadata_repository(self):
		if self._metadata_repository is None:
			from at_tools.repositories.metadata_repository import (
				MetadataRepository,
			)

			self._metadata_repository = MetadataRepository()
		return self._metadata_repository

	def analyze(self, doctype, ignored=None) -> list:
		"""Return a deduplicated list of DetectedDependency for ``doctype``."""
		meta = self.metadata_repository.get_meta(doctype)
		if not meta:
			return []

		ignored = set(ignored or [])
		ignored.add(doctype)  # self references (amended_from, parent_x) are not dependencies
		found = {}

		for df in meta.fields:
			if self.is_irrelevant(df):
				continue
			if df.fieldtype == "Link":
				self.collect(found, df, doctype, DIRECT_LINK, ignored)
			elif df.fieldtype in TABLE_FIELDTYPES and df.options:
				self.collect_child_table(found, df.options, ignored)

		return list(found.values())

	def collect_child_table(self, found, child_doctype, ignored) -> None:
		child_meta = self.metadata_repository.get_meta(child_doctype)
		if not child_meta:
			return
		for df in child_meta.fields:
			if df.fieldtype == "Link" and not self.is_irrelevant(df):
				self.collect(found, df, child_doctype, CHILD_TABLE_LINK, ignored)

	@staticmethod
	def is_irrelevant(df) -> bool:
		"""Hidden fields are never touched by the user, so they need no permission."""
		return bool(getattr(df, "hidden", 0))

	@staticmethod
	def collect(found, df, source_doctype, dependency_type, ignored) -> None:
		target = (df.options or "").strip() if isinstance(df.options, str) else ""
		if not target or target in ignored:
			return

		source = DependencySource(
			doctype=source_doctype,
			fieldname=df.fieldname,
			label=getattr(df, "label", None) or df.fieldname,
			dependency_type=dependency_type,
			reqd=int(bool(getattr(df, "reqd", 0))),
		)
		dependency = found.setdefault(target, DetectedDependency(doctype=target))
		if source not in dependency.sources:
			dependency.sources.append(source)
