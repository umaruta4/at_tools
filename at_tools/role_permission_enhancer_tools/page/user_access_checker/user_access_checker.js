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

	frappe.call({ method: `${UAC}.get_ptypes`, callback: (r) => (ptypes = r.message) });

	function load_check() {
		const user = user_field.get_value();
		const doctype = doctype_field.get_value();
		if (!user || !doctype) {
			$body.html(`<p class="text-muted">${__("Select a User and a DocType to check access.")}</p>`);
			return;
		}

		frappe.call({
			method: `${UAC}.check_user_access`,
			args: { user, doctype },
			freeze: true,
			callback: (r) => render(r.message),
		});
	}

	function render(data) {
		if (!data) {
			$body.empty();
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
