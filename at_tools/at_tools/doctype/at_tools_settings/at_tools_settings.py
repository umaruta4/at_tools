import frappe
from frappe.model.document import Document

from at_tools.tools import TOOLS, generate_hooks as _generate_hooks


@frappe.whitelist()
def generate_hooks():
	frappe.only_for("System Manager")
	return _generate_hooks()


class ATToolsSettings(Document):
	def validate(self):
		# Pastikan setiap tool di registry punya baris di settings
		existing = {row.tool for row in self.tools}
		for tool in TOOLS:
			if tool not in existing:
				self.append("tools", {"tool": tool, "enabled": 0})

	def on_update(self):
		# Jalankan installer hanya untuk tool yang baru diaktifkan
		before = self.get_doc_before_save()
		was_enabled = {row.tool for row in before.tools if row.enabled} if before else set()

		for row in self.tools:
			if row.enabled and row.tool in TOOLS and row.tool not in was_enabled and TOOLS[row.tool].get("install"):
				frappe.get_attr(TOOLS[row.tool]["install"])()
