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
	"""Used by the Employee JS to copy template rows into the Employee table."""
	frappe.has_permission("User Permission Template", "read", throw=True)
	doc = frappe.get_doc("User Permission Template", template)
	return [{field: row.get(field) for field in TEMPLATE_ITEM_FIELDS} for row in doc.items]


def sync_employee_user_permissions(doc):
	"""Reconcile the user's User Permission records with the Employee's User Permissions table."""
	if not doc.user_id:
		return

	desired = get_desired_permissions(doc.get("user_permission_items") or [], doc)
	desired_keys = {permission_key(**perm) for perm in desired}

	applied = json.loads(doc.get("user_permission_applied") or "[]")
	existing = (
		frappe.get_all(
			"User Permission",
			filters={"user": doc.user_id, "name": ["in", applied]},
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
		filters={"user": doc.user_id},
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

		up = frappe.get_doc({"doctype": "User Permission", "user": doc.user_id, **perm}).insert(
			ignore_permissions=True, ignore_if_duplicate=True
		)
		kept[key] = up.name

	# update_modified=False so the next save from the form doesn't hit a TimestampMismatchError
	applied_value = json.dumps(sorted(kept.values()))
	doc.user_permission_applied = applied_value
	frappe.db.set_value("Employee", doc.name, "user_permission_applied", applied_value, update_modified=False)


def get_desired_permissions(rows, employee):
	desired = []
	for row in rows:
		if row.value_source == "Employee Field":
			value = employee.get(row.employee_field)
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
