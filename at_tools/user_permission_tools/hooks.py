# Hooks owned by User Permission Tools. Collected into sites/.at_tools/generated_hooks.json via AT Tools Settings > Generate Hooks.
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
