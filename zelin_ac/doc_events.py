import frappe
from frappe import _
from frappe.utils import today, flt
from zelin_ac.api import get_cached_value

def stock_entry_validate(doc, method):
    set_masterial_issue_expense_account(doc)
    set_manufacture_production_cost_account(doc)

def process_item_wise_additional_cost(doc):
    flagged_additional_cost = None
    for row in doc.items:
        flagged_additional_cost = row.get('flagged_additional_cost')
        if flagged_additional_cost:
            row.additional_cost = flagged_additional_cost
    if flagged_additional_cost:
        doc.update_valuation_rate()
        doc.set_total_incoming_outgoing_value()
        doc.set_total_amount()

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

def item_price_validate(doc, method):
    """将上限数量设为下一行的等级数量，最后一行设为最大数"""
    scale_prices = doc.get('scale_prices')
    if scale_prices:
        last = len(scale_prices) - 1
        cur_qty = 0
        for (i, row) in enumerate(scale_prices):
            if row.scale_qty < cur_qty:
                frappe.throw(_('Scale Price: the {0} Row qty {1} should be bigger than previous row qty {2}'
                    ).format(i+1, row.scale_qty, cur_qty))
            cur_qty = row.scale_qty
            if i < last:
                row.upper_limit_qty = scale_prices[i+1].scale_qty
            else:
                row.upper_limit_qty = 999999999

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

def purchase_invoice_cancel(doc, method):    
    if get_cached_value('enable_purchase_invoice_variance_settlement'):
        ste_doc = frappe.db.get_value('Stock Entry', {'purchase_invoice': doc.name, 'docstatus':1})
        if ste_doc:
            frappe.get_doc('Stock Entry', ste_doc).cancel()

def purchase_invoice_submit(doc, method):
    """
    采购发票价差自动结转库存，需在中国会计设置中勾选启用，只适用于未启用批号与序列号的普通库存物料
    检查关联的采购入库日期如果可以记账（库存关帐，会计锁帐，会计期间业务交易，使用标准的价差调采购入库功能(追溯调整)
    否则创建物料移动-重新包装，将价差作为额外费用以记账日结转库存(向后适用)
    """
    
    if not get_cached_value('enable_purchase_invoice_variance_settlement'): return

    pr_details = {row.pr_detail for row in doc.items}
    if not pr_details: return

    pr = frappe.qb.DocType('Purchase Receipt')
    pri = frappe.qb.DocType('Purchase Receipt Item')
    item = frappe.qb.DocType('Item')

    pr_details = frappe.qb.from_(pr
    ).join(pri
    ).on(pr.name == pri.parent
    ).join(item
    ).on(
        (item.name == pri.item_code) &
        (item.has_batch_no==0) &    #不处理有批号与序列号的场景
        (item.has_serial_no==0)
    ).select(
        pr.name.as_('docname'),
        pr.posting_date,
        pri.item_code,
        pri.warehouse,
        (pri.billed_amt - pri.amount).as_('variance')
    ).where(
        (pri.name.isin(pr_details)) &
        ((pri.billed_amt - pri.amount) != 0) 
    ).run(as_dict=1)
    
    if not pr_details: return

    pr_adjusted = set()
    for row in pr_details:
        pr_docname = row.pr_docname
        if not pr_docname in pr_adjusted and not is_posting_date_closed(doc.company, row.posting_date):
            pr_doc = frappe.get_doc('Purchase Receipt', pr_docname)
            pr_adjusted.add(pr_docname)
    items = [row for row in pr_details if not row.pr_docname in pr_adjusted]
    create_repack_stock_entry(doc.company, doc.name, items)

def file_after_insert(doc, method):
    """
    将上传的多个ofd文件拆分到多个上传ofd单据中，分别创建日记账凭证
    """
    from zelin_ac.utils import move_file_to_sub_directory, sanitize_filename

    doctype = doc.attached_to_doctype
    if doctype and doctype in ('Import OFD', 'Invoice Recognition') and not doc.attached_to_field:
        try:        
            parsed_doc = frappe.get_doc({'doctype':doctype, 'attach': doc.file_url}).insert(ignore_permissions=1)        
            frappe.db.set_value('File', doc.name, 'attached_to_name', parsed_doc.name)
        except:
            traceback = frappe.get_traceback(with_context=True)
            frappe.log_error("zelin_ac file_after_insert ", traceback)              

    # if doctype == "Expense Claim":
    #     move_file_to_sub_directory([doc.attached_to_doctype, doc.attached_to_name], doc)
        

def file_on_trash(doc, method):
    doctype, docname = doc.attached_to_doctype, doc.attached_to_name
    if doctype and doctype not in ['Repost Item Valuation'] and docname and frappe.db.get_value(doctype, docname, 'docstatus') == 1:
        frappe.throw("不允许删除已提交单据的附件")

def get_item_wh_qty_map(item_wh_tuple):
    from pypika.terms import Tuple

    bin= frappe.qb.DocType('Bin')        
    data = frappe.qb.from_(bin
        ).select(bin.item_code,bin.warehouse,bin.actual_qty,bin.stock_value
        ).where(Tuple(bin.item_code,bin.warehouse).isin(item_wh_tuple)
        ).run(as_dict=1)
    qty_map = {(d.item_code,d.warehouse):d for d in data}
    return qty_map

@frappe.whitelist()
def create_repack_stock_entry(company, docname, items):    
    """
    将采购发票价差通过重新包装以当天记帐日期结转进库存
    前提条件：
        物料当前有库存，
        差异+库存金额为正
    """

    from frappe.utils import today, nowtime

    if not items: return

    #获取物料库存数量与金额
    item_wh_tuple = {(row.item_code,row.warehouse) for row in items}
    qty_map = get_item_wh_qty_map(item_wh_tuple)

    item_wh_data = {}
    for row in items:
        key = (row.item_code, row.warehouse)
        item_wh_data.setdefault(key, 0)
        item_wh_data[key] += row.variance
    
    stock_entry = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "purpose": "Repack",
            "stock_entry_type": "Repack",
            "posting_date": today,
            "posting_time": nowtime,
            "company": company,
            "purchase_invoice": docname
        }
    ) 
    #添加表头额外费用
    gr_ir_acct = frappe.db.get_value('Company', company, 'stock_received_but_not_billed')
    stock_entry.append('additional_costs', 
        {
            'expense_account': gr_ir_acct,
            'description': _('Settle purchase invoice variance stock'),
            'amount': sum(row.variance for row in items)                    
        }
    )

    for (key, variance) in item_wh_data.items():
        bin_data = qty_map.get(key, {})
        actual_qty = bin_data.get('actual_qty')
        stock_value = bin_data.get('stock_value')
        if actual_qty and stock_value >= variance:
            stock_entry.append('items', 
                {
                    'item_code': key[0] ,                    
                    's_warehouse': key[1],
                    'qty': actual_qty
                }
            )
            stock_entry.append('items', 
                {
                    'item_code': key[0] ,                    
                    't_warehouse': key[1],
                    'qty': actual_qty,
                    'additional_cost':variance 
                }
            )
        else:
            msg = '无库存,差异无法结转'
    if stock_entry.items:        
        stock_entry.insert(ignore_mandatory=True)
    return stock_entry

def is_posting_date_closed(company, posting_date):
    from datetime import date
    from frappe.utils import cint, add_days, getdate

    stock_settings = frappe.get_cached_doc("Stock Settings")
    if (stock_settings.stock_frozen_upto and 
        getdate(posting_date) <= getdate(stock_settings.stock_frozen_upto)):
        return  True

    stock_frozen_upto_days = cint(stock_settings.stock_frozen_upto_days)
    if (stock_frozen_upto_days and
            add_days(getdate(posting_date), stock_frozen_upto_days) <= date.today()
        ):
        return True
        
    acc_frozen_upto = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
    if acc_frozen_upto and getdate(posting_date) <= getdate(acc_frozen_upto):
        return True
    
    if frappe.db.get_all('Accounting Period',
        filters = {
            'company': company,
            'document_type': "Purchase Receipt",
            'closed':1,
            'start_date': ('<=', posting_date),
            'end_date': ('>=', posting_date),
        }
    ):        
        return True

def sales_order_before_print(doc, method, print_settings=None):
    """
    销售订单多种税率，即物料税费模板，基于系统内的json内容的物料税率提取税率赋值给含税价隐藏字段
    用于打印输出
    """

    if frappe.db.has_column('Sales Order Item', 'custom_rate_include_tax'):
        import json

        for row in doc.items:
            item_tax_rate = row.item_tax_rate
            tax_rate = 0
            if item_tax_rate and item_tax_rate != '{}':
                try:
                    tax_rate = list(json.loads(item_tax_rate).values())[0] / 100
                except:
                    frappe.msgprint(f'sales_order_before_print failed parse item_tax_rate {item_tax_rate}')
            row.custom_rate_include_tax = row.base_rate * (1+tax_rate)
            row.custom_amount_include_tax = row.base_amount * (1+tax_rate)

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

def expense_claim_before_submit(doc, method=None):
    invoices = [r.invoice_recognition for r in doc.expenses if hasattr(r, 'invoice_recognition') and r.invoice_recognition]
    if invoices:
        used_invoices = frappe.get_all('Invoice Recognition',
            filters={
                'name':('in', invoices),
                'status': ('!=', 'Recognized')
            },
            fields = ['name','status']
        )
        if used_invoices:
            msg = ','.join(f"{r.name} {_(r.status)}" for r in used_invoices)
            frappe.throw(f"关联的发票 {msg} 不是要求的已识别状态")

def validate_invoice_status(doc, method=None):
    if doc.docstatus == 1:
        for d in doc.expenses:
            if hasattr(d, 'invoice_recognition') and d.invoice_recognition:
                ir = frappe.get_doc('Invoice Recognition', d.invoice_recognition)
                ir.db_set('status','Used')
    elif doc.docstatus == 2:
        for d in doc.expenses:
            if hasattr(d, 'invoice_recognition') and d.invoice_recognition:
                ir = frappe.get_doc('Invoice Recognition', d.invoice_recognition)
                ir.db_set('status','Recognized')
    else:
        frappe.log_error('发票状态不详')

def expense_claim_after_save(doc, method=None):
    # 删除已手工删除已引用发票的明细行，更新发票状态为未使用
    frappe.db.sql("""
        UPDATE `tabMy Invoice`
        SET expense_claim = %s, expense_claim_item = %s, status = %s
        WHERE expense_claim = %s and expense_claim_item not in (select name from `tabExpense Claim Detail`)
    """ , ("", "", "未使用", doc.name))

def expense_claim_validate(doc, method=None):
    if doc.amended_from:
        for row in doc.expenses:
            if row.my_invoice_before_amend:                
                invoices = row.my_invoice_before_amend.split(',')
                can_use_invoices = frappe.get_all('My Invoice', filters = {
                        'name':('in', invoices),
                        'status': '未使用'
                    }, pluck='name'
                )
                cannot_use_invoices = set(invoices or []) - set(can_use_invoices or [])
                if cannot_use_invoices:
                    row.tax_amount = 0
                    row.my_invoice_amount = 0
                    row.invoice_code = ""
                    error_invoices = ','.join(inv for inv in cannot_use_invoices)
                    frappe.msgprint(
                        f'发票： {error_invoices} 在报销单取消与修订之间被其它报销单使用等原因不可被使用了，请重新关联发票'
                    )
                else:
                    for invoice in (can_use_invoices or []):
                        frappe.db.set_value('My Invoice', invoice, 
                            {
                                'expense_claim': doc.name,
                                'expense_claim_item': row.name,
                                'status': '已使用'
                            }
                        )
                row.my_invoice_before_amend = ""   #避免后面重复被触发

    doc.total_my_invoice_amount = sum(row.my_invoice_amount or 0 for row in doc.expenses)
    tax_amount = sum(row.deductible_tax_amount or 0 for row in doc.expenses)
    if tax_amount and tax_amount != sum(d.tax_amount for  d in doc.taxes):
        tax_account, account_name = frappe.db.get_value('Account', {
            'company': doc.company,
            'account_number': '22210101'
        },['name','account_name']) or ('','')
        if tax_account:
            doc.taxes = []
            doc.append('taxes', {
                'account_head': tax_account,
                'tax_amount': tax_amount,
                'description': account_name,
                'total':doc.total_my_invoice_amount
            })
        doc.total_taxes_and_charges = tax_amount
        doc.grand_total = (
			flt(doc.total_sanctioned_amount)
			+ flt(doc.total_taxes_and_charges)
			- flt(doc.total_advance_amount)
		)            

def expense_claim_submit_cancel(doc, method=None):
    """
    1. 保存取消前关联的发票信息，备修订时恢复
    2. 恢复发票使用状态
    """

    if method == 'on_cancel':
        my_invoice_list = frappe.get_all('My Invoice', filters={'expense_claim': doc.name},
            fields =['expense_claim_item', 'name as invoice_name'])
        if my_invoice_list:
            for row in doc.expenses:
                my_invoices = [r for r in my_invoice_list if r.expense_claim_item ==row.name]
                if my_invoices:
                    row.my_invoice_before_amend = ','.join(r.invoice_name for r in my_invoices)

            frappe.db.set_value('My Invoice', {'expense_claim': doc.name},
                {'status':'未使用', 'expense_claim': "", 'expense_claim_item':""})

def expense_claim_on_trash(doc, method=None):
    frappe.db.set_value('My Invoice', {'expense_claim': doc.name},
        {'status':'未使用', 'expense_claim': "", 'expense_claim_item':""})
        
def payment_entry_submit_cancel(doc, method=None):
    expenses = [r.reference_name for r in doc.references if r.reference_doctype == "Expense Claim"]
    if expenses:
        paid_time = today() if method == 'on_submit' else '1900-01-01'
        frappe.db.set_value('Expense Claim', {'name': ('in', expenses)}, 'paid_time', paid_time)
