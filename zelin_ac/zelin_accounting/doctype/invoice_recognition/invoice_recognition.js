// Copyright (c) 2024, xu and contributors
// For license information, please see license.txt

frappe.ui.form.on("Invoice Recognition", {
    onload(frm){
        if (!frm.doc.attach) {
            frm.get_field("preview_html").$wrapper.html('');
        }
    },
	refresh(frm) {
        if (frm.doc.__islocal) {
            let msg = __("请先保存后添加附件，系统将自动识别发票信息");
            frm.dashboard.add_comment(msg, "blue");
            frm.set_df_property(
                "preview_html",
                "hidden",
                1
            )
            if (frappe.session.user != "Administrator") {
                frappe.db.get_value("Employee", {user_id: frappe.session.user}, "name",(r) => {
                    if (r.name) {
                        frm.set_value("employee", r.name);
                    }
                });
            }
            
        } else {
            frm.set_df_property(
                "preview_html",
                "hidden",
                0
            )
        }

        if (frm.doc.attach) {
            frm.set_df_property(
                "attach",
                "hidden",
                1
            )
            frm.trigger("preview_file")
        }

        if (frm.doc.docstatus == 1 && frm.doc.status == 'Recognized') {
            frm.add_custom_button(
                __("Make Expense Claim"),
                function () {
                    frappe.call({
                        method: "zelin_ac.zelin_accounting.doctype.invoice_recognition.invoice_recognition.make_expense_claim",
                        args: {
                            args: {
                                name: frm.doc.name,
                            }                            
                        },
                        callback: function(res) {
                            if (res.message) {
                                frappe.set_route("Form", "Expense Claim", res.message.name);
                            }
                        }
                    });
                    
                },
            )

            if (frappe.user.has_role('GM')) {
                frm.add_custom_button(__('Employee'),
                    function () {
                        frappe.prompt(
                            [
                                {
                                    fieldname: "employee",
                                    label: __("Employee"),
                                    fieldtype: "Link",
                                    options: "Employee",
                                    default: frm.doc.employee,
                                    read_only: 1,
                                },
                                {
                                    fieldname: "new_employee",
                                    label: __("Employee"),
                                    fieldtype: "Link",
                                    options: "Employee",
                                    reqd: 1,
                                    get_query: () => {
                                        return {
                                            query: "erpnext.controllers.queries.employee_query",
                                            filters:{
                                                'company': frm.doc.company,
                                                'status': 'Active',
                                            }
                                        };
                                    },
                                },
                            ],
                            function (data) {
                                frappe.call({
                                    method: "zelin_ac.zelin_accounting.doctype.invoice_recognition.invoice_recognition.update_employee",
                                    args:{
                                        docname:frm.doc.name,
                                        employee: data.new_employee
                                    },
                                    callback: function(res) {
                                        if (res.message) {
                                            frappe.show_alert({ message: __('Updated Successfully'), indicator: "green" });
                                        }
                                    },
                                })
                            },
                            __("Update Employee"),
                            __("Update")
                        );
                        
                    }
                )
            }
            
        }

        if (frm.doc.docstatus == 1 && frappe.user.has_role("System Manager")) {
            frm.add_custom_button(
                __("Rerecognize"),
                function () {
                    frappe.call({
                        method: "zelin_ac.zelin_accounting.doctype.invoice_recognition.invoice_recognition.re_recognize",
                        args: {
                            docname: frm.doc.name,
                        },
                        callback: function(res) {
                            frm.reload_doc();
                        }
                    });
                    
                },
            )
        }


	},

    preview_file: function (frm) {
		let $preview = "";
		let file_extension = frm.doc.attach.split('.').pop().toLowerCase();

		if (frappe.utils.is_image_file(frm.doc.attach)) {
			$preview = $(`<div class="img_preview" style="display: flex;justify-content: center;">
				<img
					class="img-responsive shortcut-widget-box"
					src="${frappe.utils.escape_html(frm.doc.attach)}"
					onerror="${frm.toggle_display("preview", false)}"
				/>
			</div>`);
		} else if (file_extension === "pdf") {
			$preview = $(`<div class="img_preview">
				<object style="background:#323639;" width="100%">
					<embed
						style="background:#323639;"
						width="100%"
                        height="600"
						src="${frappe.utils.escape_html(frm.doc.attach)}" type="application/pdf"
					>
				</object>
			</div>`);
		} 

		if ($preview && !frm.doc.__islocal) {
			// frm.toggle_display("preview", true);
            
			frm.get_field("preview_html").$wrapper.html($preview);
		}
	},
});
