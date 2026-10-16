"""Data transfer objects used between the analyzer and the services."""

from dataclasses import asdict, dataclass, field

from at_tools.permission_dependency_manager.constants import DIRECT_LINK


@dataclass(frozen=True)
class DependencySource:
	"""One Link field that points to a dependency doctype."""

	doctype: str
	fieldname: str
	label: str = ""
	dependency_type: str = DIRECT_LINK
	reqd: int = 0

	def as_dict(self) -> dict:
		return asdict(self)


@dataclass
class DetectedDependency:
	"""A dependency doctype together with every field that references it."""

	doctype: str
	sources: list = field(default_factory=list)

	@property
	def primary(self) -> DependencySource:
		"""Direct links explain a dependency better than child table links."""
		for source in self.sources:
			if source.dependency_type == DIRECT_LINK:
				return source
		return self.sources[0]

	@property
	def reqd(self) -> int:
		return int(any(source.reqd for source in self.sources))

	def as_dict(self) -> dict:
		primary = self.primary
		return {
			"doctype": self.doctype,
			"source_doctype": primary.doctype,
			"source_field": primary.fieldname,
			"dependency_type": primary.dependency_type,
			"reqd": self.reqd,
			"sources": [source.as_dict() for source in self.sources],
		}
