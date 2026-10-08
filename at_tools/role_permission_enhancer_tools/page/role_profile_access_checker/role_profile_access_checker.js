const RPAC = "at_tools.role_permission_enhancer_tools.page.role_profile_access_checker.role_profile_access_checker";

frappe.pages["role-profile-access-checker"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Role Profile Access Checker"),
		single_column: true,
	});

	const role_profile_field = page.add_field({
		fieldname: "role_profile",
		label: __("Role Profile"),
		fieldtype: "Link",
		options: "Role Profile",
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

	frappe.call({ method: `${RPAC}.get_ptypes`, callback: (r) => (ptypes = r.message) });

	function load_check() {
		const role_profile = role_profile_field.get_value();
		const doctype = doctype_field.get_value();
		if (!role_profile) {
			$body.html(`<p class="text-muted">${__("Select a Role Profile to check access.")}</p>`);
			return;
		}

		frappe.call({
			method: `${RPAC}.check_role_profile_access`,
			args: { role_profile, doctype },
			freeze: true,
			callback: (r) => render(r.message, Boolean(doctype)),
		});
	}

	function render(data, has_doctype) {
		if (!data) {
			$body.empty();
			return;
		}

		if (!has_doctype) {
			$body.html(render_overview(data.accessible_doctypes || []));
			return;
		}

		const all_rows = [data.target, ...data.linked, ...data.settings];
		const missing_read = all_rows.filter((row) => !row.read);
		const summary = missing_read.length
			? `<div class="alert alert-warning">${__("{0} of {1} doctypes checked are missing at least Read access: {2}", [
					missing_read.length,
					all_rows.length,
					missing_read.map((row) => frappe.utils.escape_html(row.doctype)).join(", "),
				])}</div>`
			: `<div class="alert alert-success">${__("All {0} doctypes checked have at least Read access.", [all_rows.length])}</div>`;

		$body.html(`
			${summary}
			${render_section(__("Target DocType"), [data.target], false)}
			${render_section(__("Linked DocTypes"), data.linked, true)}
			${render_section(__("Related Settings"), data.settings, true)}
		`);
	}

	function render_overview(rows) {
		if (!rows.length) {
			return `<p class="text-muted">${__("This Role Profile has no Read access to any DocType.")}</p>`;
		}

		const head = ptypes.map((p) => `<th class="text-center">${__(p)}</th>`).join("");
		const body = rows
			.map(
				(row) => `<tr>
					<td>${frappe.utils.escape_html(row.doctype)}</td>
					<td>${frappe.utils.escape_html(row.module || "")}</td>
					${ptypes.map((p) => `<td class="text-center">${row[p] ? "✓" : ""}</td>`).join("")}
				</tr>`
			)
			.join("");

		return `
			<div class="mb-2 text-muted">${__("DocTypes accessible by this Role Profile ({0})", [rows.length])}</div>
			<div class="table-responsive">
				<table class="table table-bordered">
					<thead><tr><th>${__("DocType")}</th><th>${__("Module")}</th>${head}</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
			<p class="text-muted mt-2">${__("Also pick a DocType above to see its linked DocTypes and related Settings, same as the User Access Checker.")}</p>
		`;
	}

	function render_section(title, rows, show_via) {
		if (!rows.length) {
			return `<h5 class="mt-4">${title}</h5><p class="text-muted">${__("None found.")}</p>`;
		}

		const head = ptypes.map((p) => `<th class="text-center">${__(p)}</th>`).join("");
		const body = rows
			.map((row) => {
				const cells = ptypes.map((p) => `<td class="text-center">${row[p] ? "✓" : ""}</td>`).join("");
				const row_class = row.read ? "" : "table-danger";
				return `<tr class="${row_class}">
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
