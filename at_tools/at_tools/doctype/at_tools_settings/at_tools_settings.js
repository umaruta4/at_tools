frappe.ui.form.on("AT Tools Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Generate Hooks"), () => {
			frappe.call({
				method: "at_tools.at_tools.doctype.at_tools_settings.at_tools_settings.generate_hooks",
				freeze: true,
				callback(r) {
					frappe.msgprint(
						__("Generated {0}. Restart bench for the hook changes to take effect.", [r.message])
					);
				},
			});
		});
	},
});
