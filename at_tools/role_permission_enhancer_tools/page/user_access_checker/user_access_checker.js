const UAC = "at_tools.role_permission_enhancer_tools.page.user_access_checker.user_access_checker";

frappe.pages["user-access-checker"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("User Access Checker"),
		single_column: true,
	});

	const user_field = page.add_field({
		fieldname: "user",
		label: __("User"),
		fieldtype: "Link",
		options: "User",
		change: () => on_user_change(),
	});
	const role_field = page.add_field({
		fieldname: "role",
		label: __("Role"),
		fieldtype: "Autocomplete",
		description: __("Leave blank to see access combined across every role this user has."),
		change: () => load_check(),
	});
	const doctype_field = page.add_field({
		fieldname: "doctype",
		label: __("DocType"),
		fieldtype: "Link",
		options: "DocType",
		get_query: () => ({ filters: { istable: 0 } }),
		change: () => load_check(),
	});

	const $body = $('<div class="p-3"></div>').appendTo(page.main);
	let ptypes = [];
	let last_data = null;
	let edit_mode = false;

	frappe.call({ method: `${UAC}.get_ptypes`, callback: (r) => (ptypes = r.message) });

	function on_user_change() {
		exit_edit_mode();
		role_field.set_data([]);
		role_field.set_value("");

		const user = user_field.get_value();
		if (!user) {
			load_check();
			return;
		}

		frappe.call({
			method: `${UAC}.get_roles`,
			args: { user },
			callback(r) {
				role_field.set_data([
					{ value: "", label: __("All Roles (Combined)") },
					...(r.message || []).map((role) => ({ value: role, label: role })),
				]);
				load_check();
			},
		});
	}

	function load_check() {
		const user = user_field.get_value();
		const doctype = doctype_field.get_value();
		if (!user || !doctype) {
			last_data = null;
			render();
			return;
		}

		frappe.call({
			method: `${UAC}.check_user_access`,
			args: { user, doctype, role: role_field.get_value() },
			freeze: true,
			callback: (r) => {
				last_data = r.message;
				render();
			},
		});
	}

	function update_actions() {
		if (edit_mode) {
			page.set_primary_action(__("Exit Edit Mode"), () => exit_edit_mode(true), "close");
			return;
		}

		if (last_data && role_field.get_value()) {
			page.set_primary_action(__("Edit Mode"), enter_edit_mode, "edit");
		} else {
			page.clear_primary_action();
		}
	}

	function set_fields_disabled(disabled) {
		[user_field, role_field, doctype_field].forEach((field) => field.$input.prop("disabled", disabled));
	}

	function enter_edit_mode() {
		edit_mode = true;
		set_fields_disabled(true);
		render();
	}

	function exit_edit_mode(reload) {
		if (!edit_mode) return;
		edit_mode = false;
		set_fields_disabled(false);
		if (reload) {
			load_check();
		} else {
			render();
		}
	}

	$body.on("change", "input[data-ptype]", function () {
		const $checkbox = $(this);
		const value = $checkbox.prop("checked") ? 1 : 0;
		$checkbox.prop("disabled", true);
		frappe.call({
			method: `${UAC}.update_access`,
			args: {
				role: role_field.get_value(),
				doctype: $checkbox.closest("tr").data("doctype"),
				ptype: $checkbox.data("ptype"),
				value,
			},
			callback(r) {
				$checkbox.prop("disabled", false);
				if (r.exc) {
					$checkbox.prop("checked", !value);
				}
			},
		});
	});

	function render() {
		update_actions();

		if (!user_field.get_value() || !doctype_field.get_value()) {
			$body.html(`<p class="text-muted">${__("Select a User and a DocType to check access.")}</p>`);
			return;
		}

		const data = last_data;
		if (!data) {
			$body.empty();
			return;
		}

		const all_rows = [data.target, ...data.linked, ...data.settings];
		const missing_read = all_rows.filter((row) => !row.read);
		const summary = edit_mode
			? `<div class="alert alert-info">${__("Editing permissions for role {0}. Changes save immediately.", [
					frappe.utils.escape_html(role_field.get_value()),
				])}</div>`
			: missing_read.length
				? `<div class="alert alert-warning">${__(
						"{0} of {1} doctypes checked are missing at least Read access: {2}",
						[missing_read.length, all_rows.length, missing_read.map((row) => frappe.utils.escape_html(row.doctype)).join(", ")]
					)}</div>`
				: `<div class="alert alert-success">${__("All {0} doctypes checked have at least Read access.", [all_rows.length])}</div>`;

		$body.html(`
			${summary}
			${render_section(__("Target DocType"), [data.target], false)}
			${render_section(__("Linked DocTypes"), data.linked, true)}
			${render_section(__("Related Settings"), data.settings, true)}
		`);
	}

	function render_section(title, rows, show_via) {
		if (!rows.length) {
			return `<h5 class="mt-4">${title}</h5><p class="text-muted">${__("None found.")}</p>`;
		}

		const head = ptypes.map((p) => `<th class="text-center">${__(p)}</th>`).join("");
		const body = rows
			.map((row) => {
				const cells = ptypes
					.map((p) =>
						edit_mode
							? `<td class="text-center"><input type="checkbox" data-ptype="${p}" ${row[p] ? "checked" : ""}></td>`
							: `<td class="text-center">${row[p] ? "✓" : ""}</td>`
					)
					.join("");
				const row_class = !edit_mode && !row.read ? "table-danger" : "";
				return `<tr class="${row_class}" data-doctype="${frappe.utils.escape_html(row.doctype)}">
					<td>${frappe.utils.escape_html(row.doctype)}</td>
					${show_via ? `<td>${frappe.utils.escape_html(row.via || "")}</td>` : ""}
					${cells}
				</tr>`;
			})
			.join("");

		return `
			<h5 class="mt-4">${title}</h5>
			<div class="table-responsive">
				<table class="table table-bordered">
					<thead><tr><th>${__("DocType")}</th>${show_via ? `<th>${__("Via")}</th>` : ""}${head}</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`;
	}
};
