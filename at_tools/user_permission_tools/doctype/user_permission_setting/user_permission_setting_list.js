frappe.listview_settings["User Permission Setting"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Bulk Add from Template"), () => show_bulk_add_dialog(listview));
	},
};

function show_bulk_add_dialog(listview) {
	const dialog = new frappe.ui.Dialog({
		title: __("Bulk Add User Permission Settings"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "template",
				label: __("User Permission Template"),
				options: "User Permission Template",
				reqd: 1,
			},
			{
				fieldtype: "MultiSelectPills",
				fieldname: "users",
				label: __("Users"),
				reqd: 1,
				get_data(txt) {
					return frappe.db.get_link_options("User", txt, { enabled: 1 });
				},
			},
		],
		primary_action_label: __("Apply"),
		primary_action(values) {
			frappe.call({
				method: "at_tools.user_permission_tools.doctype.user_permission_setting.user_permission_setting.bulk_create_from_template",
				args: { users: JSON.stringify(values.users), template: values.template },
				freeze: true,
				callback(r) {
					dialog.hide();
					show_result(r.message);
					listview.refresh();
				},
			});
		},
	});
	dialog.show();
}

function show_result({ created, skipped, failed }) {
	let message = __("{0} created, {1} already had a User Permission Setting and were skipped.", [
		created.length,
		skipped.length,
	]);

	if (failed.length) {
		const rows = failed
			.map((f) => `<li>${frappe.utils.escape_html(f.user)}: ${frappe.utils.escape_html(f.error)}</li>`)
			.join("");
		message += `<br>${__("{0} failed:", [failed.length])}<ul>${rows}</ul>`;
	}

	frappe.msgprint({
		title: __("Bulk Add Result"),
		message,
		indicator: failed.length ? "orange" : "green",
	});
}
