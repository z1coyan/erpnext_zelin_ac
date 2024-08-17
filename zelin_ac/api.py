import frappe, json
from frappe.utils import today, flt
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

def get_cached_value(key, settings='Zelin Accounting Settings'):
    def get_value():
        return frappe.db.get_single_value(settings, key)

    return frappe.cache().get_value(key, get_value)

@frappe.whitelist()
def recognize_invoice(doc):
    def get_exp_account(expense_type):
        account = exp_account_map.get(expense_type)
        if account:
            return account
        account = frappe.db.get_value("Expense Claim Account", 
            {
                "parent": expense_type, 
                "company": doc.company
            }, 
            "default_account"
        )
        if account:
            exp_account_map[expense_type] = account
            return account

    if isinstance(doc, str):
        doc = frappe.get_doc(json.loads(doc))
    #改名前后文件内容哈希码一样，而file_url会是否有private前缀区别（通过哈希码后6位后缀区分)    
    files = frappe.get_all('File', 
        filters={
            'attached_to_doctype': doc.doctype,
            'attached_to_name': doc.name
        },
        fields = ['content_hash', 'file_url']
    )
    if not files:
        frappe.msgprint("请先上传发票")
        return doc

    exp_account_map = {}
    invoice_recognition_dt = frappe.qb.DocType('Invoice Recognition')
    file_dt = frappe.qb.DocType('File')
    recognized_invoice_map = frappe._dict(
        frappe.qb.from_(invoice_recognition_dt
        ).join(file_dt
        ).on(invoice_recognition_dt.attach==file_dt.file_url
        ).where(file_dt.content_hash.isin([f.content_hash for f in files])
        ).select(file_dt.content_hash, invoice_recognition_dt.name
        ).run(as_list=1)   
    )
    msg = []
    total_recognized_amount = 0
    doc.expenses = []
    for file in files:
        try:
            recognized_invoice_name = recognized_invoice_map.get(file.content_hash)
            if recognized_invoice_name:
                invoice_recognition_doc = frappe.get_doc('Invoice Recognition', recognized_invoice_name)                
                expense_claim = frappe.db.get_value('Expense Claim Detail', 
                    {
                        'invoice_recognition': recognized_invoice_name,
                        'docstatus':('<',2)
                    },
                    'parent'
                )
                if expense_claim:
                    msg.append(f'{invoice_recognition_doc.attach} 已被报销单 {expense_claim} 使用过 ')
                    continue
            else:            
                invoice_recognition_doc = frappe.get_doc(
                    {
                        'doctype': 'Invoice Recognition',
                        'invoice_type': 'Expense Claim',
                        'employee': doc.employee,
                        'attach': file.file_url
                    }
                ).insert(ignore_permissions=1)
            if invoice_recognition_doc.status == 'Recognize Failed' or invoice_recognition_doc.error_message:
                msg.append(f"{invoice_recognition_doc.name} {invoice_recognition_doc.attach} {invoice_recognition_doc.error_message}")
                continue

            expense_type = invoice_recognition_doc.get('expense_type') or doc.get('default_expense_type')
            account = get_exp_account(expense_type)
            doc.append("expenses",
                {
                    "expense_date": today(),
                    "expense_type": expense_type,
                    "amount": invoice_recognition_doc.grand_total,
                    "invoice_recognition": invoice_recognition_doc.name,
                    "cost_center": doc.cost_center,
                    "default_account":account,
                }
            )
            total_recognized_amount += flt(invoice_recognition_doc.grand_total)
        except:
            traceback = frappe.get_traceback(with_context=True)
            frappe.log_error("Failed Invoice Recognition for Expense Claim ", traceback)            
    doc.total_recognized_amount = total_recognized_amount
    if msg:
        msg = "\n".join(msg)
        doc.add_comment("Comment", msg)
        frappe.msgprint(msg)

    return doc