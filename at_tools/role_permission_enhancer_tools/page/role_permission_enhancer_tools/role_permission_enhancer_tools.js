const RPE = "at_tools.role_permission_enhancer_tools.page.role_permission_enhancer_tools.role_permission_enhancer_tools";

frappe.pages["role-permission-enhancer-tools"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Role Permission Enhancer Tools"),
		single_column: true,
	});

	const doctype_field = page.add_field({
		fieldname: "doctype",
		label: __("DocType"),
		fieldtype: "Link",
		options: "DocType",
		change: () => load_permissions(),
	});
	const role_field = page.add_field({
		fieldname: "role",
		label: __("Role"),
		fieldtype: "Link",
		options: "Role",
		change: () => load_permissions(),
	});

	const $body = $('<div class="p-3"></div>').appendTo(page.main);
	let ptypes = [];

	frappe.call({ method: `${RPE}.get_ptypes`, callback: (r) => (ptypes = r.message) });

	function load_permissions() {
		const doctype = doctype_field.get_value();
		const role = role_field.get_value();
		if (!doctype && !role) {
			$body.html(`<p class="text-muted">${__("Select a DocType and/or a Role to view permissions.")}</p>`);
			return;
		}

		frappe.call({
			method: `${RPE}.get_role_permissions`,
			args: { doctype, role },
			callback: (r) => render_table(r.message || []),
		});
	}

	function filter_summary() {
		const doctype = doctype_field.get_value();
		const role = role_field.get_value();
		if (doctype && role) return __("Effective permissions for {0} / {1}", [doctype, role]);
		if (doctype) return __("Effective permissions for {0}", [doctype]);
		return __("Effective permissions for role {0}", [role]);
	}

	function render_table(rows) {
		const head = ptypes.map((p) => `<th class="text-center">${__(p)}</th>`).join("");
		const body = rows
			.map((row) => {
				const cells = ptypes
					.map((p) => `<td class="text-center">${row[p] ? "✓" : ""}</td>`)
					.join("");
				const linked_button =
					row.permlevel === 0
						? `<button class="btn btn-xs btn-default btn-linked" data-doctype="${frappe.utils.escape_html(row.doctype)}" data-role="${frappe.utils.escape_html(row.role)}">${__("Linked DocTypes")}</button>`
						: "";
				return `<tr>
					<td>${frappe.utils.escape_html(row.doctype)}</td>
					<td>${frappe.utils.escape_html(row.role)}</td>
					<td class="text-center">${row.permlevel}</td>
					${cells}
					<td class="text-nowrap">
						<button class="btn btn-xs btn-default btn-set" data-doctype="${frappe.utils.escape_html(row.doctype)}" data-role="${frappe.utils.escape_html(row.role)}" data-permlevel="${row.permlevel}">${__("Set")}</button>
						${linked_button}
					</td>
				</tr>`;
			})
			.join("");

		$body.html(`
			<div class="mb-2 text-muted">${filter_summary()}</div>
			<div class="table-responsive">
				<table class="table table-bordered">
					<thead><tr><th>${__("DocType")}</th><th>${__("Role")}</th><th class="text-center">${__("Level")}</th>${head}<th></th></tr></thead>
					<tbody>${body || `<tr><td colspan="${ptypes.length + 4}" class="text-muted">${__("No permissions yet")}</td></tr>`}</tbody>
				</table>
			</div>
		`);

		$body.find("button.btn-set").on("click", function () {
			const row_doctype = $(this).data("doctype");
			const row_role = $(this).data("role");
			const row_permlevel = $(this).data("permlevel");
			open_set_dialog(
				row_doctype,
				row_role,
				row_permlevel,
				rows.find((r) => r.doctype === row_doctype && r.role === row_role && r.permlevel === row_permlevel)
			);
		});

		$body.find("button.btn-linked").on("click", function () {
			open_linked_dialog($(this).data("doctype"), $(this).data("role"));
		});
	}

	function checkbox_grid(prefix, selected, visible_ptypes = ptypes) {
		return `<div class="row">${visible_ptypes
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

	function open_set_dialog(doctype, role, permlevel, current) {
		// Frappe only honors read/write above permlevel 0 (field-level permissions).
		const visible_ptypes = permlevel > 0 ? ptypes.filter((p) => ["read", "write"].includes(p)) : ptypes;
		const selected = visible_ptypes.filter((p) => current && current[p]);
		const dialog = new frappe.ui.Dialog({
			title: __("Set Permissions: {0} / {1} (Level {2})", [role, doctype, permlevel]),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "grid" }],
			primary_action_label: __("Save"),
			primary_action(values) {
				const permissions = {};
				read_checked(dialog.$wrapper).forEach((p) => (permissions[p] = 1));
				frappe.call({
					method: `${RPE}.set_role_permissions`,
					args: { role, doctype, permissions: JSON.stringify(permissions), permlevel },
					freeze: true,
					callback() {
						dialog.hide();
						frappe.show_alert({ message: __("Permissions saved"), indicator: "green" });
						load_permissions();
					},
				});
			},
		});
		dialog.fields_dict.grid.$wrapper.html(checkbox_grid("set", selected, visible_ptypes));
		dialog.show();
	}

	function open_linked_dialog(doctype, role) {
		frappe.call({
			method: `${RPE}.get_linked_doctypes`,
			args: { doctype, role },
			callback(r) {
				const linked = r.message || [];
				if (!linked.length) {
					frappe.msgprint(__("No related DocTypes."));
					return;
				}

				const sections = linked
					.map((item) => {
						const selected = ptypes.filter((p) => item.permissions && item.permissions[p]);
						return `<div class="linked-item mb-3 p-2 border rounded" data-doctype="${item.doctype}">
							<label><input type="checkbox" class="pick" checked>
								<b>${frappe.utils.escape_html(item.doctype)}</b>
								<span class="text-muted">(${__("via")} ${frappe.utils.escape_html(item.via)})</span>
							</label>
							${checkbox_grid("linked", selected)}
						</div>`;
					})
					.join("");

				const dialog = new frappe.ui.Dialog({
					title: __("Related DocTypes for {0} / {1} (Level 0)", [doctype, role]),
					size: "extra-large",
					fields: [{ fieldtype: "HTML", fieldname: "list" }],
					primary_action_label: __("Save"),
					primary_action() {
						const items = [];
						dialog.$wrapper.find(".linked-item").each((_, el) => {
							const $el = $(el);
							if (!$el.find("input.pick").is(":checked")) return;
							const permissions = {};
							read_checked($el).forEach((p) => (permissions[p] = 1));
							items.push({ doctype: $el.data("doctype"), permissions });
						});

						if (!items.length) {
							frappe.msgprint(__("Nothing selected."));
							return;
						}

						frappe.call({
							method: `${RPE}.set_linked_permissions`,
							args: { role, items: JSON.stringify(items) },
							freeze: true,
							callback(res) {
								dialog.hide();
								frappe.show_alert({
									message: __("Permissions updated for {0} DocTypes.", [res.message]),
									indicator: "green",
								});
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
