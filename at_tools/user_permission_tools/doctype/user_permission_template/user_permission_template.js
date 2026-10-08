frappe.ui.form.on("User Permission Template", {
	setup(frm) {
		// Same lookup core's User Permission uses for its "Applicable For": only DocTypes
		// that actually link back to the row's "Allow" DocType (direct Link/Dynamic Link,
		// including via a child table).
		frm.set_query("applicable_for", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query: "frappe.core.doctype.user_permission.user_permission.get_applicable_for_doctype_list",
				filters: { doctype: row.allow },
			};
		});
	},
});
