frappe.ui.form.on('Expense Claim', {
    refresh(frm) {
        if (!frm.is_new() && !frm.is_dirty()) {
            frm.add_custom_button(__('关联发票'), () => frm.trigger('select_my_invoice'));
        }
    },
    select_my_invoice: (frm) => {
        if (frm.is_dirty()) {
            frappe.throw("请先保存单据后再关联发票！")
        }
        let expenses_data = frm.doc.expenses.map(expense => {
                const desc = expense.description? "|费用说明：" + expense.description:"";
                return expense.name + "|" + expense.idx + "|费用类型：" + expense.expense_type + "|金额：" + expense.amount + desc;
        });
        if (frm.doc.docstatus === 0){
            expenses_data.unshift('选择发票生成报销明细')   //添加第一个选项
        }
        let d = new frappe.ui.Dialog({
            title: '关联报销项对应发票',
            fields: [
                {
                    label: '关联的报销项',
                    fieldname: 'expenses',
                    fieldtype: 'Select',
                    options : expenses_data,
                    description:"选择\n由发票自动生成报销明细\n创建并选择报销明细后绑定发票",
                    reqd: 1,
                    onchange: function(values) {
                        if (event.type && event.type === 'change') {
                            get_my_invoice(frm, d);
                        }
                    }
                },
                {
                    label: '我的关联发票',
                    fieldname: 'my_used_invoice',
                    fieldtype: 'Table',
                    cannot_add_rows: true,
                    // cannot_delete_rows: true,
                    read_only: 0,
                    fields: [
                        {
                            label: '预览发票',
                            fieldname: 'view_open',
                            fieldtype: 'Button',
                            in_list_view: 1,
                            read_only: 0,
                            columns: 1,
                            click: function(row_values) {
                                var row_index = $(event.target).closest('.grid-row').data('idx');
                                var files = d.fields_dict.my_used_invoice.df.data[row_index - 1].files;
                                d.set_value('view_image','<img src="' + files + '" alt="Image">');
                                const hidden = d.get_field('view_image').df.hidden;
                                d.set_df_property("view_image", "hidden", !hidden);  //改为切换显示或隐藏
                            },
                        },
                        {
                            label: '编号',
                            fieldname: 'name',
                            fieldtype: 'Link',
                            options : "My Invoice",
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '发票类型',
                            fieldname: 'invoice_type',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '发票号',
                            fieldname: 'invoice_code',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 2,
                        },
                        {
                            label: '未税金额',
                            fieldname: 'net_amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '税额',
                            fieldname: 'tax_amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '价税合计',
                            fieldname: 'amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '发票说明',
                            fieldname: 'description',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '发票文件',
                            fieldname: 'files',
                            fieldtype: 'Data',
                            in_list_view: 0,
                            read_only: 1,
                            hidden: 1
                        },
                        {
                            label: '剔除关联',
                            fieldname: 'action_remove',
                            fieldtype: 'Button',
                            in_list_view: 1,
   			                columns: 1,
                            click: function() {
                                if (frm.doc.approval_status == "Draft" || frm.doc.approval_status == "Pending"){
                                    var row_index = $(event.target).closest('.grid-row').data('idx');
                                    frappe.call({
                                        method: 'zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.expense_remove_invoice',
                                        args: {
                                            row_values: d.fields_dict.my_used_invoice.df.data[row_index - 1],
                                            docname: frm.doc.name,
                                        },
                                        callback: function (r) {
                                            get_my_invoice(frm,d)
                                            frm.reload_doc();
                                            frm.dirty();
                                        }
                                    });
                                }else(
                                     frappe.msgprint({
                                        title: __('警告'),
                                        message: __('非草稿及审批过程中单据无法修改关联属性！'),
                                    })
                                )
                            }
                        },
                    ]
                },
                {
                    label: '我的未使用发票',
                    fieldname: 'my_invoice',
                    fieldtype: 'Table',
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    read_only: 0,
                    fields: [
                        {
                            label: '预览发票',
                            fieldname: 'view_open',
                            fieldtype: 'Button',
                            in_list_view: 1,
                            read_only: 0,
                            columns: 1,
                            click: function(row_values) {
                                var row_index = $(event.target).closest('.grid-row').data('idx');
                                var files = d.fields_dict.my_invoice.df.data[row_index - 1].files;
                                d.set_value('view_image','<img src="' + files + '" alt="Image">');
                                const hidden = d.get_field('view_image').df.hidden;
                                d.set_df_property("view_image", "hidden", !hidden);  //改为切换显示或隐藏
                            },
                        },
                        {
                            label: '编号',
                            fieldname: 'name',
                            fieldtype: 'Link',
                            options : "My Invoice",
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '发票类型',
                            fieldname: 'invoice_type',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '发票号',
                            fieldname: 'invoice_code',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 2
                        },
                        {
                            label: '未税金额',
                            fieldname: 'net_amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '税额',
                            fieldname: 'tax_amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '价税合计',
                            fieldname: 'amount',
                            fieldtype: 'Float',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 1
                        },
                        {
                            label: '发票说明',
                            fieldname: 'description',
                            fieldtype: 'Data',
                            in_list_view: 1,
                            read_only: 1,
                            columns: 2
                        },
                        {
                            label: '发票文件',
                            fieldname: 'files',
                            fieldtype: 'Data',
                            in_list_view: 0,
                            read_only: 1,
                            hidden: 1
                        },
                    ]
                },
                {
                    label: '预览发票',
                    fieldname: 'view_image',
                    fieldtype: 'HTML',
                    read_only: 1,
                    hidden: 1,
                },
            ],
            size: 'extra-large', //extra-large
            primary_action_label: '关联',
            primary_action(values) {
                var expenses = d.get_field("expenses").get_value();
                var expense_claim_item = expenses.split("|")[0].trim();
                var data = {items: d.fields_dict.my_invoice.grid.get_selected_children()};
                if (!data.items.length){
                    frappe.msgprint('请先勾选我的未使用发票后再点关联按钮')
                } else {
                    frappe.call({
                        method: 'zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.expense_select_invoice',
                        args: {
                            docname: frm.doc.name,
                            expense_claim_item: expense_claim_item,
                            items: data,
                        },
                        callback: function (r) {
                            if (expense_claim_item==="选择发票生成报销明细"){
                                d.hide();                                
                            } else {
                                get_my_invoice(frm,d)
                            }
                            frm.reload_doc();
                            frm.dirty();
                        }
                    });
                }
                // d.hide();
            },
            secondary_action_label: '关闭弹窗',
            secondary_action(values) {
                d.hide();
            }
        });
        d.fields_dict.my_invoice.grid.grid_pagination.page_length = 5
        d.fields_dict.my_used_invoice.grid.grid_pagination.page_length = 5
        //if (frm.doc.approval_status == "Not Paid" || frm.doc.approval_status == "Paid"){
        if (frm.doc.docstatus > 0){         //提交或取消后隐藏分派我的发票明细表
            d.$wrapper.find('.standard-actions').hide()
            d.set_df_property("my_invoice", "hidden", 1);
            //d.layout.primary_button?.hide();
        }
        d.show();
    }
});

frappe.ui.form.on('Expense Claim Detail', {
    expenses_remove(frm, cdt, cdn) {
        var row = locals[cdt][cdn]
        frappe.call({
            method: "zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.get_my_used_invoice",
            args: {
                doc_name: frm.doc.name,
                expense_claim_item: cdn
            },
            freeze: true,
            callback: function (r) {
                var my_used_invoice_data = r.message
                if(my_used_invoice_data.length >= 1){
                    frm.reload_doc();
                    frappe.msgprint("无法删除已关联发票的报销项，请在关联发票中先剔除关联的发票再试！")
                }
            }
        })
    }
})


function get_my_invoice(frm,d) {
    remove_all_rows(d)
    d.set_df_property("view_image", "hidden", 1);
    var expenses = d.get_field("expenses").get_value();
    var expense_claim_item = expenses.split("|")[0].trim();
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "My Invoice",
            filters: { "employee":frm.doc.employee, "status":"未使用"},
            fields: ['name', 'invoice_type', 'invoice_code', 'net_amount', 'tax_amount', 'amount', 'description', 'files'],
            limit_page_length: 500
        },
        callback: function (r) {
            var my_invoice_data = r.message
            const my_invoice_list = my_invoice_data.map(data => {
                return {
                    name: data.name,
                    invoice_type: data.invoice_type,
                    invoice_code: data.invoice_code,
                    net_amount: data.net_amount,
                    tax_amount: data.tax_amount,
                    amount: data.amount,
                    description: data.description,
                    files: data.files,
                    view_image: data.files
                };
            });
            // d.fields_dict.my_invoice.grid.refresh();
            d.fields_dict.my_invoice.df.data = my_invoice_list;
            d.fields_dict.my_invoice.grid.refresh();
            // d.fields_dict.my_invoice.grid.wrapper.find('.row-check.sortable-handle.col').hide()
            // d.wrapper.find('.first-page, .prev-page, .next-page, .last-page').on('click', function() {
            //     d.fields_dict.my_invoice.grid.wrapper.find('.row-check.sortable-handle.col').hide()
            // });
        }
    }), 
    frappe.call({
        method: 'zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.get_my_used_invoice',
        args: {
            doc_name: frm.doc.name,
            expense_claim_item: expense_claim_item
        },
        callback: function (r) {
            var my_used_invoice_data = r.message
            const my_used_invoice_list = my_used_invoice_data.map(data => {
                return {
                    name: data[0],
                    invoice_type: data[1],
                    invoice_code: data[2],
                    net_amount: data[3],
                    tax_amount: data[4],
                    amount: data[5],
                    description: data[6],
                    files: data[7]
                };
            });
            // 计算合计值
            const total = {
                net_amount: my_used_invoice_list.reduce((acc, cur) => acc + parseFloat(cur.net_amount || 0), 0),
                tax_amount: my_used_invoice_list.reduce((acc, cur) => acc + parseFloat(cur.tax_amount || 0), 0),
                amount: my_used_invoice_list.reduce((acc, cur) => acc + parseFloat(cur.amount || 0), 0),
                name: "小计："
            };

            // 添加合计行到列表末尾
            my_used_invoice_list.push(total);
            d.fields_dict.my_used_invoice.df.data = my_used_invoice_list;
            d.fields_dict.my_used_invoice.grid.refresh();
        }
    })
}

function remove_all_rows(d) {
    var rows = d.fields_dict.my_used_invoice.grid.grid_rows;
    var i = rows.length - 1;
    while (i >= 0) {
        rows[i].remove();
        rows = d.fields_dict.my_used_invoice.grid.grid_rows; // 重新获取行的数量
        i = rows.length - 1;
    }
    var rows = d.fields_dict.my_invoice.grid.grid_rows;
    var i = rows.length - 1;
    while (i >= 0) {
        rows[i].remove();
        rows = d.fields_dict.my_invoice.grid.grid_rows; // 重新获取行的数量
        i = rows.length - 1;
    }
}