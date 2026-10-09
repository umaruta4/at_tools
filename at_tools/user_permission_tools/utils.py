import json

import frappe

from at_tools.tools import is_tool_enabled

TEMPLATE_ITEM_FIELDS = [
	"allow",
	"applicable_for",
	"apply_to_all_documents",
	"value_source",
	"fixed_value",
	"employee_field",
]


@frappe.whitelist()
def get_template_items(template):
	"""Used by the User Permission Setting JS to copy template rows into its items table."""
	frappe.has_permission("User Permission Template", "read", throw=True)
	doc = frappe.get_doc("User Permission Template", template)
	return [{field: row.get(field) for field in TEMPLATE_ITEM_FIELDS} for row in doc.items]


def delete_applied_user_permissions(doc):
	"""Delete every User Permission this tool created and is tracking for this User Permission
	Setting. Called from on_trash, since once the Setting is deleted there's nothing left to
	reconcile `applied` against - unlike a normal save, every tracked User Permission must go."""
	for name in json.loads(doc.get("applied") or "[]"):
		if frappe.db.exists("User Permission", name):
			frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)


def sync_user_permissions(doc):
	"""Reconcile the User's User Permission records with this User Permission Setting's items table."""
	desired = get_desired_permissions(doc.get("items") or [], doc.user)
	desired_keys = {permission_key(**perm) for perm in desired}

	applied = json.loads(doc.get("applied") or "[]")
	existing = (
		frappe.get_all(
			"User Permission",
			filters={"user": doc.user, "name": ["in", applied]},
			fields=["name", "allow", "for_value", "applicable_for", "apply_to_all_doctypes"],
		)
		if applied
		else []
	)

	# Only keep UPs this tool created. Ones matching desired are kept, the rest are deleted.
	kept = {}
	for row in existing:
		key = permission_key(row.allow, row.for_value, row.applicable_for, row.apply_to_all_doctypes)
		if key in desired_keys and key not in kept:
			kept[key] = row.name
		else:
			frappe.delete_doc("User Permission", row.name, ignore_permissions=True, force=True)

	# UPs that already exist from other sources (e.g. ERPNext or manual) are never recreated or managed by this tool
	current_user_permissions = frappe.get_all(
		"User Permission",
		filters={"user": doc.user},
		fields=["allow", "for_value", "applicable_for", "apply_to_all_doctypes"],
	)
	current_keys = {
		permission_key(r.allow, r.for_value, r.applicable_for, r.apply_to_all_doctypes)
		for r in current_user_permissions
	}

	for perm in desired:
		key = permission_key(**perm)
		if key in kept or key in current_keys:
			continue

		up = frappe.get_doc({"doctype": "User Permission", "user": doc.user, **perm}).insert(
			ignore_permissions=True, ignore_if_duplicate=True
		)
		kept[key] = up.name

	# update_modified=False so the next save from the form doesn't hit a TimestampMismatchError
	applied_value = json.dumps(sorted(kept.values()))
	doc.applied = applied_value
	frappe.db.set_value(doc.doctype, doc.name, "applied", applied_value, update_modified=False)


def get_desired_permissions(rows, user):
	"""Resolve each row's value: "Fixed Value" rows use fixed_value directly; "Employee Field"
	rows look up that field on the Employee linked to `user` (via user_id) - fetched lazily, once,
	only if a row actually needs it. UserPermissionSetting.validate() already guarantees such an
	Employee exists whenever any row uses "Employee Field", but a specific field on it can still
	be blank, in which case that row is skipped (not an error, same as a blank Fixed Value)."""
	desired = []
	employee = None
	employee_loaded = False

	for row in rows:
		if row.value_source == "Employee Field":
			if not employee_loaded:
				employee = frappe.db.get_value("Employee", {"user_id": user}, "*", as_dict=True)
				employee_loaded = True
			value = (employee or {}).get(row.employee_field)
		else:
			value = row.fixed_value

		if not value:
			continue

		desired.append(
			{
				"allow": row.allow,
				"for_value": str(value),
				"applicable_for": row.applicable_for or None,
				"apply_to_all_doctypes": 1 if row.apply_to_all_documents else 0,
			}
		)
	return desired


def permission_key(allow, for_value, applicable_for, apply_to_all_doctypes):
	return (allow, str(for_value), applicable_for or "", int(apply_to_all_doctypes or 0))


def is_enabled():
	return is_tool_enabled("User Permission Tools")
