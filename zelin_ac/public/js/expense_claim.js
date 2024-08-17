frappe.ui.form.on('Expense Claim',{
	refresh : function(frm) {
		frm.set_query("invoice_recognition","expenses", function(doc, cdt, cdn) {
			let d = locals[cdt][cdn];

			return {
				query: "zelin_ac.zelin_accounting.doctype.invoice_recognition.invoice_recognition.invoice_recogniton_query",
				filters: {
					"company": frm.doc.company,
					"grand_total": d.amount,
					"employee": frm.doc.employee,
					"expense_type": d.expense_type,
				}
			};
		});

		// 预览发票
		const invoice_recognition = frm.doc.expenses.filter((row) => row.invoice_recognition)
		if (!frm.doc.__islocal && invoice_recognition.length) {
			frm.add_custom_button(__('Preview Invoice'),
				function() { 
					preview_all_invoice(frm)
				 },);
		}		
	},

	employee: function(frm) {
		if (frm.doc.docstatus == 0 && frm.doc.company && frm.doc.employee) {
			frm.trigger('add_ir_button');
		}
	},

	add_ir_button: function(frm) {
		frm.add_custom_button(__("Get Invoice Recognition"), function() {
			frm.trigger('get_invoice_recognition');
		}) 
	},

	onload_post_render(frm){
		const btn_field = frm.get_field('recognize_invoice')
		btn_field && btn_field.$input && btn_field.$input.addClass('btn-primary');		
	},
		
	recognize_invoice: function(frm) {
		frappe.call({
			method: "zelin_ac.api.recognize_invoice",
			freeze: true,
			freeze_message: __("发票识别中..."),
			args:{"doc": frm.doc},
			callback: function(r) {
				frappe.model.sync(r.message);
				refresh_field("expenses");
				refresh_field("total_recognized_amount");
				frm.dirty();
			}
		})
	},

	get_invoice_recognition: function(frm) {
		frappe.call({
			method: "zelin_ac.zelin_accounting.doctype.invoice_recognition.invoice_recognition.get_invoice_recognition",
			args:{
				"company": frm.doc.company,
				"employee": frm.doc.employee,
			},
			callback: function(r) {
				let ir_list = r.message;
				var d = new frappe.ui.Dialog({
					title:__("Get Invoice Recognition"),
					fields: [
						{
							label:__("Project"),
							fieldtype:"Link",
							fieldname:"project",
							options:"Project",
							reqd: 0,
							description:'选择项目，用以筛选发票',
							onchange: function(frm) {
								ir_filtered = ir_list.filter(item => item.project ==  d.get_values()['project'])
								let field = d.get_field("invoice_recognition");
								field.df.data = ir_filtered;
								field.refresh();
							}
						},
						{
							label: __("Invoice Recognition"),
							fieldtype: 'Table',
							fieldname: 'invoice_recognition',
							cannot_add_rows:1,
							"read_only": 1,
							description: '已提交，还未使用或者报销单还没有完成审批的发票，点击蓝色按钮预览发票',
							fields: [{
								fieldtype: 'Button',
								fieldname: 'name',
								"read_only": 1,
								label: __('Preview'),
								in_list_view: 1,
								columns:1,
								click: function(row) {
									var row_index = $(event.target).closest('.grid-row').data('idx');
									console.log(row_index)
									var file_url = d.fields_dict.invoice_recognition.df.data[row_index - 1].attach;
									let preview_html = preview_invoice(file_url)
									let field = d.get_field("preview_html");
									field.df.options = field.html(preview_html);
								},
								formatter: function(value, row, column, data, default_formatter) {  
									return `<span style = "padding: 5px;" class="btn-primary">${value}</span>`;  
								}  
							}, {
								fieldtype: 'Link',
								fieldname: 'project',
								"read_only": 1,
								label: __('Project'),
								in_list_view: 1,
								columns:1
							}, {
								fieldtype: 'Link',
								fieldname: 'company',
								"read_only": 1,
								label: __('Company'),
								in_list_view: 0,
								columns:1
							}, {
								fieldname: "column_break_5",
								fieldtype: "Column Break",
							}, {
								fieldtype: 'Link',
								fieldname: 'employee',
								"read_only": 1,
								label: __('Employee'),
								in_list_view: 0,
								columns:1
							}, {
								fieldtype: 'Date',
								fieldname: 'invoice_date',
								label: __('Invoice Date'),
								"read_only": 1,
								in_list_view: 1,
								columns:1
							}, {
								fieldtype: 'Link',
								fieldname: 'expense_type',
								options: 'Expense Claim Type',
								"read_only": 1,
								label: __('Expense Claim Type'),
								in_list_view: 1,
								columns:1
							}, {
								fieldname: "column_break_5",
								fieldtype: "Column Break",
							}, {
								fieldtype: 'Currency',
								fieldname: 'grand_total',
								label: __('Grand Total'),
								"read_only": 1,
								in_list_view: 1,
								columns:1
							}, {
								fieldtype: 'Currency',
								fieldname: 'total_tax',
								label: __('Total Tax'),
								"read_only": 1,
								in_list_view: 1,
								columns:1
							}, {
								fieldtype: 'Data',
								fieldname: 'invoice_type_org',
								label: __('Invoice Type Org'),
								"width": 1,
								"read_only": 1,
								in_list_view: 1,
								columns:1
							}, {
								fieldname: "column_break_5",
								fieldtype: "Column Break",
							}, {
								fieldtype: 'Data',
								fieldname: 'party',
								"read_only": 1,
								label: __('Party'),
								in_list_view: 1,
								columns:1
							}, {
								fieldtype: 'Data',
								fieldname: 'invoice_code',
								"read_only": 1,
								label: __('Invoice Code'),
								in_list_view: 0,
								columns:1
							}, {
								fieldtype: 'Data',
								fieldname: 'invoice_num',
								"read_only": 1,
								label: __('Invoice Num'),
								in_list_view: 1,
								columns:1,
							}, {
								fieldtype: 'Link',
								fieldname: 'attach',
								"read_only": 1,
								options: 'File',
								label: __('Attach'),
								in_list_view: 0,
								columns:1
						}],
						data: ir_list,
						},
						{
							label:__("Preview"),
							fieldtype:"HTML",
							fieldname:"preview_html",
						},

					],
					primary_action_label: __("Make Expense Claim"),
					primary_action: function() {
						var ir_list = d.fields_dict.invoice_recognition.grid.get_selected_children();
						if (ir_list.length == 0) {
							frappe.throw('请勾选发票')
						}
						frappe.call({
							method: "zelin_ac.zelin_accounting.doctype.invoice_recognition.invoice_recognition.make_expense_claim",
							args: {
								args: ir_list,
							},
							callback: function(res) {
								if (res.message) {
									frappe.set_route("Form", "Expense Claim", res.message.name);
								}
							}
						});

						d.hide()
					},
				})
				d.show()
				d.$wrapper.find('.modal-dialog').css("max-width", "90%");
			}
		})
	},
})

function preview_invoice  (url) {
	let preview = "";
	let file_extension = url.split('.').pop().toLowerCase();

	if (frappe.utils.is_image_file(url)) {
		preview = `<div class="img_preview" style="display: flex;justify-content: center;">
			<img
				class="img-responsive shortcut-widget-box"
				src="${frappe.utils.escape_html(url)}"
			/>
		</div>`;
	} else if (file_extension === "pdf") {
		preview = `<div class="img_preview links-widget-box input">
			<object style="background:#323639;" width="100%">
				<embed
					style="background:#323639;"
					width="100%"
					height="600"
					src="${frappe.utils.escape_html(url)}" type="application/pdf"
				>
			</object>
		</div>`;
	} 

	return preview;
};

function preview_all_invoice (frm) {
	let preview = "";
	frm.doc.expenses.forEach(item => {
		if (item.invoice_recognition) {
			preview += preview_invoice(item.file_url)
		}
	})

	var d = new frappe.ui.Dialog({
		title:__("Invoice Recognition"),
		fields: [
			{
				label:__("Preview"),
				fieldtype:"HTML",
				fieldname:"preview_html",
				options: preview,
			}
		],
		primary_action_label: "关闭",
		primary_action: function() {
			d.hide()
		}
	})
	
	d.show();
	d.$wrapper.find('.modal-dialog').css("max-width", "90%");
};