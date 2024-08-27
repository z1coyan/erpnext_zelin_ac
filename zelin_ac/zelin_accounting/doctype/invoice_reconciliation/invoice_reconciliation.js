frappe.ui.form.on('Invoice Reconciliation', {
	setup: (frm) => {
        frm.custom_make_buttons = {
            'Reconciliation Invoice': 'Reconciliation Invoice'
        };
    },
 	onload: (frm) => {
   		if (frm.is_new()) {
           frm.set_value("reconciliation_date", frappe.datetime.get_today());
    	}
  	},
	refresh: (frm) => {
        frm.add_custom_button(__('核销发票'), () => frm.trigger('Reconciliation_invoice'), __('Actions'));
    },
	Reconciliation_invoice: (frm) => {
        let d = new frappe.ui.Dialog({
            title: '获取发票',
            fields: [
                {
                    label: '付款时间',
                    fieldname: 'paid_date',
                    fieldtype: 'Date Range',
                    onchange: function(values) {
                        if (event.type && event.type === 'click') {
                            get_paid_invoice(frm, d);
                        }
                    }
                },
                {
                    label: '未核销发票',
                    fieldname: 'invoices',
                    fieldtype: 'Table',
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    fields: [
                        {
                            label: '发票号',
                            fieldname: 'invoice_name',
                            fieldtype: 'Link',
                            options: "My Invoice",
                            in_list_view: 1,
                            read_only: 1,
                            columns: 2,
                        },
                        {
                            label: '发票类型',
                            fieldname: 'invoice_type',
                            fieldtype: 'Link',
                            options: "My Invoice Type",
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1,
                        },
                        {
                            label: '未税金额',
                            fieldname: 'net_amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1,
                        },
                        {
                            label: '税额',
                            fieldname: 'tax_amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1,
                        },
                        {
                            label: '价税合计',
                            fieldname: 'amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1,
                        },
                        {
                            label: '发票编号',
                            fieldname: 'invoice_code',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 2,
                        },
                        {
                            label: '发票备注',
                            fieldname: 'description',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 2,
                        },
                        {
                            label: '文件目录',
                            fieldname: 'files',
                            fieldtype: 'Data',
                            in_list_view: 0,
                            read_only: 1,
                        },
                        {
                            label: '费用报销单',
                            fieldname: 'expense_claim',
                            fieldtype: 'Link',
                            options: "Expense Claim",
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1,
                        },
                        {
                            label: '费用报销明细',
                            fieldname: 'expense_claim_item',
                            fieldtype: 'Data',
                            in_list_view: 0,
                            read_only: 1,
                        },
                        {
                            label: '所属人',
                            fieldname: 'owner_user',
                            fieldtype: 'Link',
                            options: "User",
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1,
                        }
                    ],
                }
            ],
            size: 'extra-large', // small, large, extra-large
            secondary_action_label: '核销勾选发票',
            secondary_action(values) {
                console.log(values);
                reconcile_selected_invoices(frm, d);
                d.hide();
            },
            primary_action_label: '核销全部发票',
            primary_action(values) {
                reconcile_all_invoices(frm, d);
                d.hide();
            }
        });
        d.show();

    }
    })


function get_paid_invoice(frm,d) {
    remove_all_rows(d)
    d.fields_dict.invoices.grid.grid_pagination.page_length = 15
    var start_date = d.get_field("paid_date").get_value()[0];
    var end_date = d.get_field("paid_date").get_value()[1];
    frappe.call({
        method: 'zelin_ac.zelin_accounting.doctype.invoice_reconciliation.invoice_reconciliation.get_paid_invoice',
        args: {
            start_date: start_date,
            end_date: end_date
        },
        callback: function (r) {
            var paid_invoice_data = r.message
            const paid_invoice_list = paid_invoice_data.map(data => {
                return {
                    invoice_name: data[0],
                    invoice_type: data[1],
                    net_amount: data[2],
                    tax_amount: data[3],
                    amount: data[4],
                    invoice_code: data[5],
                    description: data[6],
                    files: data[7],
                    expense_claim: data[8],
                    expense_claim_item : data[9],
                    owner_user: data[10],
                };
            });
            d.fields_dict.invoices.df.data = paid_invoice_list;
            d.fields_dict.invoices.grid.refresh();
        }
    })
}



function remove_all_rows(d) {
    var rows = d.fields_dict.invoices.grid.grid_rows;
    var i = rows.length - 1;
    while (i >= 0) {
        rows[i].remove();
        rows = d.fields_dict.invoices.grid.grid_rows; // 重新获取行的数量
        i = rows.length - 1;
    }
}


function reconcile_selected_invoices(frm, d) {
    // const selected_rows = d.fields_dict.invoices.grid.get_selected();
    var selected_rows = d.fields_dict.invoices.grid.get_selected_children();
    selected_rows.forEach(data => {
        frm.add_child('items', {
            invoice_name: data.invoice_name,
            invoice_type: data.invoice_type,
            net_amount: data.net_amount,
            tax_amount: data.tax_amount,
            amount: data.amount,
            invoice_code: data.invoice_code,
            description: data.description,
            files: data.files,
            expense_claim: data.expense_claim,
            expense_claim_item: data.expense_claim_item,
            owner_user: data.owner_user,
        });
    });
    frm.refresh_field('items');
}

function reconcile_all_invoices(frm, d) {
    const all_data = d.fields_dict.invoices.df.data;
    all_data.forEach(data => {
        frm.add_child('items', {
            invoice_name: data.invoice_name,
            invoice_type: data.invoice_type,
            net_amount: data.net_amount,
            tax_amount: data.tax_amount,
            amount: data.amount,
            invoice_code: data.invoice_code,
            description: data.description,
            files: data.files,
            expense_claim: data.expense_claim,
            expense_claim_item: data.expense_claim_item,
            owner_user: data.owner_user,
        });
    });
    frm.refresh_field('items');
}