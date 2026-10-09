import frappe
from frappe import _
from frappe.model.document import Document

from at_tools.user_permission_tools.utils import (
	delete_applied_user_permissions,
	get_template_items,
	is_enabled,
	sync_user_permissions,
)


class UserPermissionSetting(Document):
	def validate(self):
		uses_employee_field = any(row.value_source == "Employee Field" for row in self.items)
		if uses_employee_field and not frappe.db.exists("Employee", {"user_id": self.user}):
			frappe.throw(
				_(
					"User {0} has no linked Employee record, but one or more rows use "
					"'Employee Field' as their Value Source."
				).format(self.user)
			)

	def on_update(self):
		if not is_enabled():
			return

		sync_user_permissions(self)

	def on_trash(self):
		delete_applied_user_permissions(self)


@frappe.whitelist()
def bulk_create_from_template(users, template):
	"""Create a User Permission Setting (with `template`'s rows) for every user in `users` that
	doesn't already have one. A user that already has a User Permission Setting is skipped -
	this never overwrites an existing one, edit it directly on its own form instead.

	Each user is created and committed on its own, so one user's validation failure (e.g. an
	"Employee Field" row but no Employee linked to that user) is reported back without blocking
	the rest of the batch.
	"""
	frappe.has_permission("User Permission Setting", "create", throw=True)
	if not frappe.db.exists("User Permission Template", template):
		frappe.throw(_("User Permission Template {0} not found").format(template))

	items = get_template_items(template)

	created, skipped, failed = [], [], []
	for user in frappe.parse_json(users):
		if not frappe.db.exists("User", user):
			failed.append({"user": user, "error": _("User not found")})
			continue

		if frappe.db.exists("User Permission Setting", user):
			skipped.append(user)
			continue

		try:
			frappe.get_doc(
				{
					"doctype": "User Permission Setting",
					"user": user,
					"user_permission_template": template,
					"items": [dict(row) for row in items],
				}
			).insert()
			frappe.db.commit()
			created.append(user)
		except Exception as e:
			frappe.db.rollback()
			failed.append({"user": user, "error": str(e)})

	return {"created": created, "skipped": skipped, "failed": failed}
