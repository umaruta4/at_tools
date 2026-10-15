/**
 * Permission Dependency Manager
 *
 * Extends the native Role Permission Manager page (frappe.PermissionEngine) with a
 * "Dependencies" action next to the Delete button. Loaded through the `page_js` hook,
 * so nothing in frappe/erpnext is modified. Works on v15 and v16: both versions render
 * the row actions through PermissionEngine.add_delete_button(row, d).
 */
frappe.provide("permission_dependency_manager");

(function (pdm) {
	const API = "at_tools.api.role_permission.";
	const PTYPES = ["read", "select", "create", "write", "delete", "submit", "cancel", "amend"];
	const STATUS = {
		satisfied: { label: __("Satisfied"), color: "green" },
		partial: { label: __("Partial"), color: "orange" },
		missing: { label: __("Missing"), color: "red" },
		disabled: { label: __("Disabled"), color: "gray" },
	};
	const esc = (value) => frappe.utils.escape_html(String(value == null ? "" : value));
	const title = (ptype) => __(toTitle(ptype));

	// ------------------------------------------------------------ page injection

	pdm.patch_engine = function () {
		const Engine = frappe.PermissionEngine;
		if (!Engine || Engine.prototype.__pdm_patched) return;
		Engine.prototype.__pdm_patched = true;

		if (typeof Engine.prototype.add_delete_button === "function") {
			const add_delete_button = Engine.prototype.add_delete_button;
			Engine.prototype.add_delete_button = function (row, d) {
				const out = add_delete_button.apply(this, arguments);
				try {
					pdm.add_button(this, row.find(".btn-remove-perm"), d.parent, d.role, d.permlevel);
				} catch (e) {
					console.error("Permission Dependency Manager", e); // never break the native page
				}
				return out;
			};
			return;
		}

		// Fallback for a future refactor: decorate rows after the table is rendered.
		const show_permission_table = Engine.prototype.show_permission_table;
		if (typeof show_permission_table !== "function") return;
		Engine.prototype.show_permission_table = function () {
			const out = show_permission_table.apply(this, arguments);
			try {
				const engine = this;
				this.body.find(".btn-remove-perm").each(function () {
					const $btn = $(this);
					pdm.add_button(
						engine,
						$btn,
						$btn.attr("data-doctype"),
						$btn.attr("data-role"),
						$btn.attr("data-permlevel")
					);
				});
			} catch (e) {
				console.error("Permission Dependency Manager", e);
			}
			return out;
		};
	};

	pdm.add_button = function (engine, $delete_btn, doctype, role, permlevel) {
		if (!$delete_btn.length || cint(permlevel) !== 0 || !doctype || !role) return;
		if ($delete_btn.siblings(".btn-perm-dependency").length) return;

		$delete_btn.parent().css("white-space", "nowrap");
		$(
			`<button class="btn btn-default btn-xs btn-perm-dependency" style="margin-right: 6px;"
				title="${esc(__("Permission Dependencies"))}">${__("Dependency")}</button>`
		)
			.insertBefore($delete_btn)
			.on("click", () => {
				new pdm.DependencyDialog({ engine, doctype, role }).show();
				return false;
			});
	};

	// -------------------------------------------------------------------- dialog

	pdm.DependencyDialog = class DependencyDialog {
		constructor({ engine, doctype, role }) {
			this.engine = engine;
			this.doctype = doctype;
			this.role = role;
			this.rows = [];
			this.only_open = false;
			this.search = "";
		}

		show() {
			this.dialog = new frappe.ui.Dialog({
				title: __("Permission Dependencies — {0}", [__(this.doctype)]),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "body" }],
				primary_action_label: __("Apply Permissions"),
				primary_action: () => this.apply(),
				secondary_action_label: __("Save Configuration"),
				secondary_action: () =>
					this.save().then(() => {
						frappe.show_alert({ message: __("Configuration saved"), indicator: "green" });
						this.load();
					}),
			});
			this.$body = this.dialog.fields_dict.body.$wrapper;
			this.bind_events();
			this.dialog.show();
			this.load();
		}

		load() {
			this.$body.html(`<div class="text-muted text-center" style="padding: 40px;">${__("Loading")}…</div>`);
			return frappe
				.call({ method: API + "get_dependencies", args: { role: this.role, doctype: this.doctype } })
				.then((r) => {
					this.rows = (r.message && r.message.dependencies) || [];
					this.render();
				});
		}

		// ---------------------------------------------------------------- render

		status_of(row) {
			if (row.configured && !row.enabled) return "disabled";
			const required = PTYPES.filter((p) => row.permissions[p]);
			const granted = required.filter((p) => row.current_permissions[p]);
			if (granted.length === required.length) return "satisfied";
			return granted.length ? "partial" : "missing";
		}

		visible_rows() {
			const search = this.search.toLowerCase();
			return this.rows.filter((row) => {
				if (search && !row.doctype.toLowerCase().includes(search)) return false;
				if (this.only_open && !["missing", "partial"].includes(this.status_of(row))) return false;
				return true;
			});
		}

		render() {
			const selected = this.rows.filter((row) => row.enabled).length;
			this.$body.html(`
				<div class="flex justify-between align-center" style="gap: 12px; margin-bottom: 12px;">
					<div class="text-muted small">
						${__("Role")}: <b>${esc(__(this.role))}</b> ·
						${__("{0} detected or configured, {1} selected", [this.rows.length, selected])}<br>
						${__("Detected dependencies are recommendations. Only selected rows are granted, and existing permissions are never removed.")}
					</div>
					<div class="flex align-center" style="gap: 12px; white-space: nowrap;">
						<input type="text" class="form-control input-xs pdm-search" style="width: 180px;"
							placeholder="${esc(__("Search doctype"))}" value="${esc(this.search)}">
						<label class="small" style="margin: 0;">
							<input type="checkbox" class="pdm-only-open" ${this.only_open ? "checked" : ""}>
							${__("Missing only")}
						</label>
					</div>
				</div>
				<div class="table-responsive" style="max-height: 60vh; overflow-y: auto;">
					<table class="table table-bordered small" style="margin-bottom: 0;">
						<thead><tr>
							<th style="width: 32px;"><input type="checkbox" class="pdm-toggle-all" title="${esc(
								__("Select all visible rows")
							)}"></th>
							<th>${__("Doctype")}</th>
							<th>${__("Source Field")}</th>
							<th>${__("Type")}</th>
							<th>${__("Current")}</th>
							<th>${__("Permission to Grant")}</th>
							<th>${__("Status")}</th>
							<th style="width: 64px;"></th>
						</tr></thead>
						<tbody class="pdm-rows"></tbody>
					</table>
				</div>
				<div style="margin-top: 12px;">
					<button class="btn btn-default btn-xs pdm-add">+ ${__(
				"Add Dependency"
			)}</button>
				</div>`);
			this.render_rows();
		}

		render_rows() {
			const rows = this.visible_rows();
			const $tbody = this.$body.find(".pdm-rows").empty();
			if (!rows.length) {
				$tbody.append(
					`<tr><td colspan="8" class="text-muted text-center">${__("No dependencies to show.")}</td></tr>`
				);
				return;
			}
			rows.forEach((row) => $tbody.append(this.row_html(row)));
		}

		row_html(row) {
			const status = STATUS[this.status_of(row)];
			const current = PTYPES.filter((p) => row.current_permissions[p]).map(title);
			const recommended = PTYPES.filter((p) => row.recommended_permissions[p]).map(title);
			const more = (row.sources || []).length - 1;
			const source = row.source && row.source.fieldname
				? `${row.source.doctype !== this.doctype ? esc(row.source.doctype) + " · " : ""}<code>${esc(
						row.source.fieldname
				  )}</code>${more > 0 ? ` <span class="text-muted">+${more}</span>` : ""}`
				: `<span class="text-muted">${esc(row.reason || "—")}</span>`;
			const chips = PTYPES.map(
				(p) =>
					`<span class="indicator-pill no-indicator-dot pdm-chip ${row.permissions[p] ? "blue" : "gray"}"
						data-ptype="${p}" style="cursor: pointer; margin: 0 4px 4px 0; user-select: none;">${title(p)}</span>`
			).join("");

			return `<tr data-doctype="${esc(row.doctype)}" class="${row.enabled ? "" : "text-muted"}">
				<td><input type="checkbox" class="pdm-enabled" ${row.enabled ? "checked" : ""}></td>
				<td><b>${esc(__(row.doctype))}</b>${row.reqd ? ` <span class="text-danger" title="${esc(
				__("Mandatory field")
			)}">*</span>` : ""}
					<div class="text-muted">${esc(__(row.classification))}</div></td>
				<td>${source}</td>
				<td>${esc(__(row.dependency_type))}</td>
				<td>${current.length ? esc(current.join(" + ")) : "—"}</td>
				<td>${chips}<div class="text-muted">${__("Recommended")}: ${esc(recommended.join(" + ") || "—")}</div></td>
				<td><span class="indicator-pill ${status.color}">${status.label}</span></td>
				<td style="white-space: nowrap;">
					<button class="btn btn-default btn-xs pdm-explain" title="${esc(__("Explain Dependency"))}">?</button>
					${
						row.configured || row.source_type === "Manual"
							? `<button class="btn btn-default btn-xs pdm-remove" title="${esc(
									__("Remove configuration")
							  )}">&times;</button>`
							: ""
					}
				</td>
			</tr>`;
		}

		// ---------------------------------------------------------------- events

		row_for(el) {
			const doctype = $(el).closest("tr").attr("data-doctype");
			return this.rows.find((row) => row.doctype === doctype);
		}

		bind_events() {
			const me = this;
			this.$body
				.on("click", ".pdm-chip", function () {
					const row = me.row_for(this);
					const ptype = $(this).attr("data-ptype");
					row.permissions[ptype] = row.permissions[ptype] ? 0 : 1;
					if (row.permissions[ptype]) row.enabled = 1;
					me.render_rows();
				})
				.on("change", ".pdm-enabled", function () {
					me.row_for(this).enabled = this.checked ? 1 : 0;
					me.render_rows();
				})
				.on("change", ".pdm-toggle-all", function () {
					me.visible_rows().forEach((row) => (row.enabled = this.checked ? 1 : 0));
					me.render_rows();
				})
				.on("change", ".pdm-only-open", function () {
					me.only_open = this.checked;
					me.render_rows();
				})
				.on("input", ".pdm-search", function () {
					me.search = this.value || "";
					me.render_rows();
				})
				.on("click", ".pdm-explain", function () {
					me.explain(me.row_for(this));
				})
				.on("click", ".pdm-remove", function () {
					me.remove(me.row_for(this));
				})
				.on("click", ".pdm-add", () => this.add_manual());
		}

		explain(row) {
			const lines = (row.sources || []).map(
				(s) => `<li><code>${esc(s.doctype)}.${esc(s.fieldname)}</code> → ${esc(row.doctype)}
					<span class="text-muted">(${esc(__(s.dependency_type))}${s.reqd ? ", " + __("mandatory") : ""})</span></li>`
			);
			frappe.msgprint({
				title: __("Explain Dependency — {0}", [__(row.doctype)]),
				indicator: "blue",
				message: `${lines.length ? `<ul>${lines.join("")}</ul>` : ""}
					<p><b>${__("Reason")}:</b><br>${esc(row.reason || row.explanation || __("Added manually.")).replace(
					/\n/g,
					"<br>"
				)}</p>`,
			});
		}

		add_manual() {
			frappe.prompt(
				[
					{
						fieldname: "dependency_doctype",
						fieldtype: "Link",
						options: "DocType",
						label: __("Dependency Doctype"),
						reqd: 1,
						get_query: () => ({ filters: { istable: 0, name: ["!=", this.doctype] } }),
					},
					{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason") },
				],
				(values) => {
					const existing = this.rows.find((row) => row.doctype === values.dependency_doctype);
					if (existing) {
						existing.enabled = 1;
						if (values.reason) existing.reason = values.reason;
						return this.render();
					}
					frappe
						.call({
							method: API + "get_existing_permissions",
							args: { role: this.role, doctypes: [values.dependency_doctype] },
						})
						.then((r) => {
							const permissions = {};
							PTYPES.forEach((p) => (permissions[p] = p === "read" ? 1 : 0));
							this.rows.push({
								doctype: values.dependency_doctype,
								source: {},
								sources: [],
								source_type: "Manual",
								dependency_type: "Manual",
								classification: "",
								configured: 0,
								enabled: 1,
								reqd: 0,
								reason: values.reason || "",
								explanation: "",
								permissions,
								recommended_permissions: Object.assign({}, permissions),
								current_permissions: r.message[values.dependency_doctype] || {},
							});
							this.render();
						});
				},
				__("Add Dependency"),
				__("Add")
			);
		}

		remove(row) {
			const drop = () => {
				if (row.source_type === "Manual") {
					this.rows = this.rows.filter((other) => other !== row);
					return this.render();
				}
				return this.load();
			};
			if (!row.configured) return drop();
			frappe.confirm(
				__("Remove the saved configuration for {0}? Native permissions are not changed.", [
					__(row.doctype),
				]),
				() =>
					frappe
						.call({
							method: API + "remove_dependency",
							args: { role: this.role, doctype: this.doctype, dependency_doctype: row.doctype },
						})
						.then(drop)
			);
		}

		// --------------------------------------------------------------- actions

		payload() {
			return this.rows.map((row) => ({
				dependency_doctype: row.doctype,
				enabled: row.enabled ? 1 : 0,
				permissions: PTYPES.filter((p) => row.permissions[p]),
				reason: row.reason || "",
			}));
		}

		save() {
			return frappe.call({
				method: API + "save_dependency_configuration",
				args: { role: this.role, doctype: this.doctype, dependencies: this.payload() },
				freeze: true,
			});
		}

		apply() {
			const pending = this.rows.filter((row) => {
				return row.enabled && PTYPES.some((p) => row.permissions[p] && !row.current_permissions[p]);
			});
			if (!pending.length) {
				return this.save().then(() => {
					frappe.show_alert({ message: __("Nothing to grant. Configuration saved."), indicator: "blue" });
					this.load();
				});
			}

			const list = pending
				.map((row) => {
					const add = PTYPES.filter((p) => row.permissions[p] && !row.current_permissions[p]);
					return `<li><b>${esc(__(row.doctype))}</b>: ${esc(add.map(title).join(" + "))}</li>`;
				})
				.join("");

			frappe.confirm(
				`${__("Grant the following permissions to role {0}?", [`<b>${esc(__(this.role))}</b>`])}
				<ul style="max-height: 40vh; overflow-y: auto; margin-top: 8px;">${list}</ul>`,
				() =>
					this.save()
						.then(() =>
							frappe.call({
								method: API + "apply_dependencies",
								args: { role: this.role, doctype: this.doctype },
								freeze: true,
								freeze_message: __("Applying permissions"),
							})
						)
						.then((r) => {
							const changed = ((r.message && r.message.changed) || []).length;
							frappe.show_alert({
								message: __("Permissions granted on {0} doctype(s)", [changed]),
								indicator: "green",
							});
							this.load();
							this.engine && this.engine.refresh && this.engine.refresh();
						})
			);
		}
	};

	pdm.patch_engine();
})(permission_dependency_manager);
