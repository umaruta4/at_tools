# Hooks milik User Permission Tools. Dikumpulkan ke generated_hooks.py lewat AT Tools Settings > Generate Hooks.
HOOKS = {
	"doc_events": {
		"Employee": {
			"on_update": "at_tools.user_permission_tools.doc_events.erpnext.employee.on_update",
		},
	},
	"doctype_js": {
		"Employee": "public/js/user_permission_tools/erpnext/employee.js",
	},
}
