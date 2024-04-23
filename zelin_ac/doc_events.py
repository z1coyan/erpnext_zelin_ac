import frappe


def stock_entry_validate(doc, method):
    set_masterial_issue_expense_account(doc)
    set_manufacture_production_cost_account(doc)

def subcontracting_receipt_validate(doc, method):
    # 14版委外入库明细行还没有采购订单明细字段
    if not hasattr(doc.items[0], 'purchase_order_item'):
        return
    account_map = frappe._dict(frappe.get_all("Purchase Order Item",
        filters = {'name': ('in', 
            {row.purchase_order_item for row in doc.items if row.purchase_order_item})
        },
        fields = ['name', 'expense_account'],
        as_list = 1
    ))
    if account_map:
        for row in doc.items:
            expense_account = account_map.get(row.purchase_order_item)
            if expense_account:
                row.expense_account = expense_account

def process_return_doc_status(doc, method):
    doctype = doc.doctype
    item_field_name = 'dn_detail' if doctype=='Delivery Note' else 'purchase_receipt_item'
    return_against = doc.return_against
    if doc.is_return and return_against:
        #获取被退货明细
        returned_items = {d.get(item_field_name) for d in doc.items}
        #检查被退货明细是否存在至少草稿状态的销售发票
        invoiced = frappe.db.exists("Sales Invoice Item", 
            {
                'docstatus':("<", 2),
                item_field_name: ('in', returned_items)
            }
        )
        if not invoiced:
            if method == 'on_submit':
                #因退货数量将在源出库单开票时被扣减，修改本退货单可开票状态，避免重复开票(退款)
                frappe.db.set_value(doctype, doc.name, {'per_billed': 100,'status':'Completed'})
                returned_doc = frappe.db.get_value(doctype, return_against, ['status', 'per_returned'], as_dict=1)
                #如果被退货出库单被全部退货则通过修改状态隐藏下推发票按钮
                if (returned_doc.status == 'Return Issued' and 
                    frappe.utils.flt(returned_doc.per_returned) >= 100.0):
                    frappe.db.set_value(doctype, return_against, 'status', 'Closed')
            elif method == 'on_cancel':
                returned_doc = frappe.get_doc(doctype, return_against)
                if returned_doc.status == 'Closed':
                    returned_doc.status = None
                    returned_doc.set_status(update=True)    #恢复未退货前状态

def set_masterial_issue_expense_account(doc):
    if doc.stock_entry_type in ['Material Issue', 'Material Receipt'] and doc.reason_code:
        expense_account = doc.expense_account
        if not expense_account:
            expense_account = frappe.db.get_value('Material Movement Default Account',
                {'company': doc.company,
                 'parent': doc.reason_code
                },
                'expense_account'
            )
        if expense_account:
            for row in doc.items:
                row.expense_account = expense_account

def set_manufacture_production_cost_account(doc):
    if doc.stock_entry_type == 'Manufacture':
        production_input_account, production_output_account = frappe.db.get_value('Company',
            doc.company, ['production_input_account', 'production_output_account'])
        if production_input_account or production_output_account:
            for row in doc.items:
                if row.is_finished_item and production_output_account:
                    row.expense_account = production_output_account
                elif row.s_warehouse and production_input_account:
                    row.expense_account = production_input_account