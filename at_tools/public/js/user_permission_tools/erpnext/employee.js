frappe.ui.form.on("Employee", {
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
					frm.clear_table("user_permission_items");
					(r.message || []).forEach((row) => frm.add_child("user_permission_items", row));
					frm.refresh_field("user_permission_items");
					frm._prev_user_permission_template = template;
				},
			});
		};

		if (frm.doc.user_permission_items && frm.doc.user_permission_items.length) {
			frappe.confirm(
				__("Ganti baris User Permissions dengan isi template?"),
				copy_items,
				() => {
					// Batal: kembalikan template sebelumnya tanpa memicu handler ini lagi
					frm.doc.user_permission_template = frm._prev_user_permission_template;
					frm.refresh_field("user_permission_template");
				}
			);
		} else {
			copy_items();
		}
	},
});
