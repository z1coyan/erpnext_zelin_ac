import frappe, json
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

@frappe.whitelist()
def create_sales_invoice(source_names):
    """
    source_names: [{"delivery_note":"DN-24-00036","child_name":"71530848a1"}]
    dn_childnames_map:{"DN-24-00036":{"71530848a1"}}
    """    
    source_names =json.loads(source_names)
    dn_childnames_map = {}
    for item in source_names:
        childnames = dn_childnames_map.setdefault(item["delivery_note"], set())
        childname = item.get("child_name")
        if childname:
            childnames.add(childname)

    #检查是否有草稿状态的发票
    filters= {'docstatus': 0}
    childnames = {r.get("child_name") for r in source_names if r.get("child_name")}
    if childnames:
        filters['dn_detail'] = ('in', childnames)
    else:
        filters['delivery_note'] = ('in', {r["delivery_note"] for r in source_names})
    draft_inv_dn = frappe.get_all("Sales Invoice Item", filters= filters, distinct=1,
        fields=['parent as invoice','delivery_note']
    )
    if draft_inv_dn:
        msg = ','.join([f"{r.invoice},{r.delivery_note}" for r in draft_inv_dn])
        frappe.msgprint(f'草稿状态发票已包括所选出库单{msg}')
        return

    items, non_billable, non_billable_child,  = [], [], []
    for (dn, childnames) in dn_childnames_map.items():
        sales_invoice = make_sales_invoice(dn)
        if sales_invoice and sales_invoice.items:
            if childnames:
                #标准代码按dn创建发票，仅保留选择的待开票明细行
                cur_items = [row for row in sales_invoice.items if row.dn_detail in childnames]
                dn_details = {row.dn_detail for row in sales_invoice.items}
                if [childname for childname in childnames if childname not in dn_details]:
                    non_billable_child.append(dn)
            else:
                cur_items = sales_invoice.items 
            items.extend(cur_items)            
        else:
            non_billable.append(dn)
    if sales_invoice and items:
        sales_invoice.items = items
        # 混合模式不勾选 退款
        if sales_invoice.is_return and any(row.qty>0 for row in items):
            sales_invoice.is_return = 0
        sales_invoice.calculate_taxes_and_totals()
        if non_billable or non_billable_child:
            msg = ''
            if non_billable:
                msg = f'出库单{",".join(non_billable)}无可开票明细'
            if non_billable_child:
                msg = f"{msg} 生成的发票剔除了出库单{','.join(non_billable_child)}中不可开票明细"
            frappe.msgprint(msg, alert = True)    
        return sales_invoice
    else:
        frappe.msgprint("选择的出库单无可开票明细")