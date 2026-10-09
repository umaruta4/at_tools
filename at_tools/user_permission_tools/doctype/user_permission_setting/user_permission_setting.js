frappe.ui.form.on("User Permission Setting", {
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

	refresh(frm) {
		frm._prev_user_permission_template = frm.doc.user_permission_template;
	},

	user_permission_template(frm) {
		const template = frm.doc.user_permission_template;
		if (!template) {
			frm._prev_user_permission_template = template;
			return;
		}

		const copy_items = () => {
			frappe.call({
				method: "at_tools.user_permission_tools.utils.get_template_items",
				args: { template },
				callback(r) {
					frm.clear_table("items");
					(r.message || []).forEach((row) => frm.add_child("items", row));
					frm.refresh_field("items");
					frm._prev_user_permission_template = template;
				},
			});
		};

		if (frm.doc.items && frm.doc.items.length) {
			frappe.confirm(
				__("Replace the User Permissions rows with the template's content?"),
				copy_items,
				() => {
					// Cancelled: restore the previous template without re-triggering this handler
					frm.doc.user_permission_template = frm._prev_user_permission_template;
					frm.refresh_field("user_permission_template");
				}
			);
		} else {
			copy_items();
		}
	},
});
