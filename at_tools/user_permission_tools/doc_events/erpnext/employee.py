from at_tools.user_permission_tools.utils import is_enabled, sync_employee_user_permissions


def on_update(doc, method=None):
	if not is_enabled():
		return

	sync_employee_user_permissions(doc)
