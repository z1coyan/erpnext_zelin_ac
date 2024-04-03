/* 这种写法会覆盖掉标准自带的代码
frappe.listview_settings['Delivery Note'] = {
    refresh: function(doclist) {
        doclist.page.add_action_item(__('Create One Sales Invoice'), () => create_sales_invoice(doclist));
    }
}
*/

const original_refresh = frappe.listview_settings['Delivery Note']["refresh"];
frappe.listview_settings['Delivery Note']["refresh"] = function(doclist) {
    original_refresh && original_refresh(doclist);
    doclist.page.add_action_item(__('Create One Sales Invoice'), () => create_sales_invoice(doclist));
}

var create_sales_invoice = function (doclist) {
    let source_names = doclist.get_checked_items().map(function(d) {
        return {
            'delivery_note': d["name"],
            'customer': d["customer"],
            'child_name': d["Delivery Note Item:name"]
        };
    });

/*     
    if (! source_names[0].child_name){
        frappe.msgprint("请确保在报表视图界面且报表输出字段中至少包括了一个出库明细字段")
        return
    } 
*/

    const uniqueCustomer = source_names.reduce((set, row) => set.add(row.customer), new Set());
    if (uniqueCustomer.size > 1){
        frappe.msgprint("请选择同一个客户的出库存单");
        return
    }
    frappe.call({
        method: "zelin_ac.api.create_sales_invoice",
        args: {
            source_names: source_names
        },
        callback: function(r) {
            if (r.message) {
                var doclist = frappe.model.sync(r.message);
                frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
            }
        }
    })
}