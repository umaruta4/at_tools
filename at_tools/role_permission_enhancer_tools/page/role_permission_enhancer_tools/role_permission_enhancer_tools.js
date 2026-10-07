const RPE = "at_tools.role_permission_enhancer_tools.utils";

frappe.pages["role-permission-enhancer-tools"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Role Permission Enhancer Tools"),
		single_column: true,
	});

	const role_field = page.add_field({ fieldname: "role", label: __("Role"), fieldtype: "Link", options: "Role" });
	const doctype_field = page.add_field({
		fieldname: "doctype",
		label: __("DocType"),
		fieldtype: "Link",
		options: "DocType",
		change: () => load_permissions(),
	});

	const $body = $('<div class="p-3"></div>').appendTo(page.main);
	let ptypes = [];

	page.set_primary_action(__("Linked DocTypes"), () => open_linked_dialog(), "octicon octicon-link");

	frappe.call({ method: `${RPE}.get_ptypes`, callback: (r) => (ptypes = r.message) });

	function load_permissions() {
		const doctype = doctype_field.get_value();
		if (!doctype) {
			$body.html(`<p class="text-muted">${__("Select a DocType to view its permissions.")}</p>`);
			return;
		}

		frappe.call({
			method: `${RPE}.get_role_permissions`,
			args: { doctype },
			callback: (r) => render_table(doctype, r.message || []),
		});
	}

	function render_table(doctype, rows) {
		const head = ptypes.map((p) => `<th class="text-center">${__(p)}</th>`).join("");
		const body = rows
			.map((row) => {
				const cells = ptypes
					.map((p) => `<td class="text-center">${row[p] ? "✓" : ""}</td>`)
					.join("");
				return `<tr>
					<td>${frappe.utils.escape_html(row.role)}</td>
					<td class="text-center">${row.permlevel}</td>
					${cells}
					<td><button class="btn btn-xs btn-default" data-role="${frappe.utils.escape_html(row.role)}">${__("Set")}</button></td>
				</tr>`;
			})
			.join("");

		$body.html(`
			<div class="mb-2 text-muted">${__("Effective permissions for {0}", [doctype])}</div>
			<div class="table-responsive">
				<table class="table table-bordered">
					<thead><tr><th>${__("Role")}</th><th class="text-center">${__("Level")}</th>${head}<th></th></tr></thead>
					<tbody>${body || `<tr><td colspan="${ptypes.length + 3}" class="text-muted">${__("No permissions yet")}</td></tr>`}</tbody>
				</table>
			</div>
		`);

		$body.find("button[data-role]").on("click", function () {
			open_set_dialog(doctype, $(this).data("role"), rows.find((r) => r.role === $(this).data("role")));
		});
	}

	function checkbox_grid(prefix, selected) {
		return `<div class="row">${ptypes
			.map(
				(p) => `<div class="col-sm-3"><label class="mb-2 d-block">
					<input type="checkbox" data-ptype="${p}" ${selected.includes(p) ? "checked" : ""}> ${__(p)}
				</label></div>`
			)
			.join("")}</div>`;
	}

	function read_checked(container) {
		return container
			.find("input[data-ptype]:checked")
			.map((_, el) => $(el).data("ptype"))
			.get();
	}

	function open_set_dialog(doctype, role, current) {
		const selected = ptypes.filter((p) => current && current[p]);
		const dialog = new frappe.ui.Dialog({
			title: __("Set Permissions: {0} / {1}", [role, doctype]),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "grid" }],
			primary_action_label: __("Save"),
			primary_action(values) {
				const permissions = {};
				read_checked(dialog.$wrapper).forEach((p) => (permissions[p] = 1));
				frappe.call({
					method: `${RPE}.set_role_permissions`,
					args: { role, doctype, permissions: JSON.stringify(permissions) },
					freeze: true,
					callback() {
						dialog.hide();
						frappe.show_alert({ message: __("Permissions saved"), indicator: "green" });
						load_permissions();
					},
				});
			},
		});
		dialog.fields_dict.grid.$wrapper.html(checkbox_grid("set", selected));
		dialog.show();
	}

	function open_linked_dialog() {
		const doctype = doctype_field.get_value();
		const role = role_field.get_value();
		if (!doctype || !role) {
			frappe.msgprint(__("Select a Role and a DocType first."));
			return;
		}

		frappe.call({
			method: `${RPE}.get_linked_doctypes`,
			args: { doctype },
			callback(r) {
				const linked = r.message || [];
				if (!linked.length) {
					frappe.msgprint(__("No related DocTypes."));
					return;
				}

				const sections = linked
					.map(
						(item) => `<div class="linked-item mb-3 p-2 border rounded" data-doctype="${item.doctype}">
							<label><input type="checkbox" class="pick" checked>
								<b>${frappe.utils.escape_html(item.doctype)}</b>
								<span class="text-muted">(${__("via")} ${frappe.utils.escape_html(item.via)})</span>
							</label>
							${checkbox_grid("linked", ["select", "read"])}
						</div>`
					)
					.join("");

				const dialog = new frappe.ui.Dialog({
					title: __("Related DocTypes for {0}", [doctype]),
					size: "extra-large",
					fields: [{ fieldtype: "HTML", fieldname: "list" }],
					primary_action_label: __("Apply to {0}", [role]),
					primary_action() {
						const items = [];
						dialog.$wrapper.find(".linked-item").each((_, el) => {
							const $el = $(el);
							if (!$el.find("input.pick").is(":checked")) return;
							const permissions = {};
							read_checked($el).forEach((p) => (permissions[p] = 1));
							if (Object.keys(permissions).length) {
								items.push({ doctype: $el.data("doctype"), permissions });
							}
						});

						if (!items.length) {
							frappe.msgprint(__("Nothing selected."));
							return;
						}

						frappe.call({
							method: `${RPE}.grant_linked_permissions`,
							args: { role, items: JSON.stringify(items) },
							freeze: true,
							callback(res) {
								dialog.hide();
								frappe.msgprint(__("Permissions added to {0} DocTypes.", [res.message]));
								load_permissions();
							},
						});
					},
				});
				dialog.fields_dict.list.$wrapper.html(sections);
				dialog.show();
			},
		});
	}
};
