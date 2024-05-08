# Copyright (c) 2024, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.query_builder.functions import Sum, Avg
from erpnext.accounts.report.general_ledger.general_ledger import get_gl_entries


def execute(filters=None):
    columns = get_column()
    data = get_data(filters)
    return columns, data

def get_data(filters):
    gr_ir_acct = frappe.db.get_value('Company', filters.company, 'stock_received_but_not_billed')
    if not gr_ir_acct:
        frappe.throw('公司主数据未维护默认暂估库存(已收货，未开票)科目')
    filters.account = gr_ir_acct    

    gl_entries = get_gl_entries(filters, accounting_dimensions = [])

    pr = frappe.qb.DocType('Purchase Receipt')
    pri = frappe.qb.DocType('Purchase Receipt Item')
    pi = frappe.qb.DocType('Purchase Invoice')
    pii = frappe.qb.DocType('Purchase Invoice Item')

    suppliers = filters.supplier if filters.supplier else None
    pi_amount, pr_amount = {}, {}
    for entry in gl_entries:
        voucher_no = entry.voucher_no
        if entry.get('voucher_type') =='Purchase Invoice':
            pi_amount.setdefault(voucher_no, 0) 
            pi_amount[voucher_no] += entry.debit - entry.credit
        elif entry.get('voucher_type') =='Purchase Receipt':
            pr_amount.setdefault(voucher_no, 0) 
            pr_amount[voucher_no] += entry.debit - entry.credit 

    data = []
    pr_detail_in_pi = set()
    if pi_amount:
        query = frappe.qb.from_(pii
        ).join(pi
        ).on(pii.parent == pi.name
        ).select(
            pi.name.as_('purchase_invoice'),
            pi.supplier,
            pi.supplier_name,
            pi.posting_date.as_('pi_date'),
            pii.item_code,
            pii.item_name,
            pii.pr_detail,
            Sum(pii.qty).as_('pi_qty'),
            Avg(pii.base_net_rate).as_('pi_rate'),
            Sum(pii.base_net_amount).as_('pi_item_amount')
        ).groupby(
            pi.supplier, pi.name, pii.item_code, pii.item_name, pii.pr_detail
        ).where(
            pi.name.isin(list(pi_amount))
        )
        if suppliers:
            query = query.where(pi.supplier.isin(suppliers))
        data = query.run(as_dict=1)
        pr_detail_in_pi = {d.pr_detail for d in data}
        for d in data:
            d.pi_amount = pi_amount.get(d.purchase_invoice)

    if pr_amount:
        query = frappe.qb.from_(pri
        ).join(pr
        ).on(pri.parent == pr.name
        ).select(
            pr.name.as_('purchase_receipt'),
            pr.supplier,
            pr.supplier_name,
            pr.posting_date.as_('pr_date'),
            pr.status.as_('pr_status'),
            pri.idx.as_('pr_item_idx'),
            pri.item_code,
            pri.item_name,
            pri.name.as_('pr_detail'),
            Sum(pri.qty).as_('pr_qty'),
            Avg(pri.base_net_rate).as_('pr_rate'),
            Sum(pri.base_net_amount).as_('pr_item_amount')
        ).groupby(
            pr.supplier, pr.status, pr.name,pri.idx, pri.item_code, pri.item_name, pri.name
        ).where(
            (pr.name.isin(list(pr_amount))) &
            (pri.allow_zero_valuation_rate == 0)
        )
        if suppliers:
            query = query.where(pr.supplier.isin(suppliers))
        pr_data = query.run(as_dict=1)
        for d in pr_data:
            d.pr_amount = pr_amount.get(d.purchase_receipt, 0)
        pr_detail_dict = {d.pr_detail:d for d in pr_data}

        #发票匹配入库
        for d in data:
            pr_detail = pr_detail_dict.get(d.pr_detail)
            if pr_detail:
                for f in ['purchase_receipt', 'pr_date', 'pr_status','pr_item_idx', 
                    'pr_qty','pr_rate','pr_item_amount','pr_amount']:
                    d[f] = pr_detail[f]
        
        #有入库无发票
        data.extend([d for d in pr_data if d.pr_detail not in pr_detail_in_pi])

        #计算差异
        for d in data:
            d.variance = flt(d.get('pi_item_amount', 0) - d.get('pr_item_amount', 0),2)
            
        if filters.hide_fully_matched:
            data = [d for d in data if flt(d.variance,0) != 0]

    return data

def get_column():
    return [
        {
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 100,
        },
        {
            "label": _("Supplier Name"),
            "fieldname": "supplier_name",
            "fieldtype": "Data",            
            "width": 120,
        },
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 180,
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "hidden": 1,
            "width": 130,
        },
        {
            "label": _("Purchase Receipt"),
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 130,
        },
        {
            "label": _("PR Status"),
            "fieldname": "pr_status",
            "fieldtype": "Data",            
            "width": 100,
        },
        {
            "label": _("PR Detail"),
            "fieldname": "pr_detail",
            "fieldtype": "Data", 
            "hidden": 1,           
            "width": 100,
        }, 
        {
            "label": _("PR Item Idx"),
            "fieldname": "pr_item_idx",
            "fieldtype": "Data",            
            "width": 90,
        },                
        {"label": _("PR Date"), "fieldname": "pr_date", "fieldtype": "Date", "width": 120},
        {
            "label": _("PR Qty"),
            "fieldname": "pr_qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("PR Rate"),
            "fieldname": "pr_rate",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("PR Item Amount"),
            "fieldname": "pr_item_amount",
            "fieldtype": "Currency",
            "width": 100,
            "options": "Company:company:default_currency",
        },
        {
            "label": _("PR Amount"),
            "fieldname": "pr_amount",
            "fieldtype": "Currency",
            "width": 100,
            "options": "Company:company:default_currency",
        },           
        {
            "label": _("Purchase Invoice"),
            "fieldname": "purchase_invoice",
            "fieldtype": "Link",
            "options": "Purchase Invoice",
            "width": 140,
        },       
        {"label": _("PI Date"), "fieldname": "pi_date", "fieldtype": "Date", "width": 120},
        {
            "label": _("PI Qty"),
            "fieldname": "pi_qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("PI Rate"),
            "fieldname": "pi_rate",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("PI Item Amount"),
            "fieldname": "pi_item_amount",
            "fieldtype": "Currency",
            "width": 100,
            "options": "Company:company:default_currency",
        },
        {
            "label": _("PI Amount"),
            "fieldname": "pi_amount",
            "fieldtype": "Currency",
            "width": 100,
            "options": "Company:company:default_currency",
        },  
        {"label": _("Variance"), "fieldname": "variance", "fieldtype": "Float", "width": 120}        
    ]

    
"""
for testing 
from frappe import _
from frappe.query_builder.functions import Sum, Avg
from erpnext.accounts.report.general_ledger.general_ledger import get_gl_entries
filters= frappe._dict(
    {"company":"则霖信息技术（深圳）有限公司",
    "from_date":"2024-04-08",
    "to_date":"2024-05-08",
    "party":["水电公司","新供应商"],
    "hide_fully_matched":1}
)
"""