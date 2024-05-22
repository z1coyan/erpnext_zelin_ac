# Copyright (c) 2024, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.query_builder.functions import Sum, Avg
from frappe.query_builder.custom import ConstantColumn
from frappe.model.meta import get_field_precision
from erpnext.accounts.report.general_ledger.general_ledger import get_result


def execute(filters=None):
    columns = get_column()
    data = get_data(filters)
    return columns, data

def get_data(filters):
    gr_ir_acct = frappe.db.get_value('Company', filters.company, 'stock_received_but_not_billed')
    if not gr_ir_acct:
        frappe.throw('公司主数据未维护默认暂估库存(已收货，未开票)科目')
    filters.account = gr_ir_acct    
    filters.group_by = "Group by Voucher (Consolidated)" 
    gl_entries = get_result(filters, {})
    #剔除期初、期末数据
    gl_entries = [entry for entry in gl_entries if entry.get('gl_entry')]

    pr = frappe.qb.DocType('Purchase Receipt')
    pri = frappe.qb.DocType('Purchase Receipt Item')
    pi = frappe.qb.DocType('Purchase Invoice')
    pii = frappe.qb.DocType('Purchase Invoice Item')
 
    suppliers = filters.supplier if filters.supplier else None
    extended_match = filters.extended_match
    pi_amount, pr_amount, pr_detail_dict, po_detail_dict, pr_data, pr_data_by_po_detail = {}, {}, {},{}, [], []
    for entry in gl_entries:
        voucher_no = entry.voucher_no
        if entry.get('voucher_type') =='Purchase Invoice':
            pi_amount.setdefault(voucher_no, 0) 
            pi_amount[voucher_no] += entry.debit - entry.credit
        elif entry.get('voucher_type') =='Purchase Receipt':
            pr_amount.setdefault(voucher_no, 0) 
            pr_amount[voucher_no] += entry.debit - entry.credit 

    data = []
    pr_detail_in_pi,po_detail_in_pi = set(), set()
    
    pi_query = frappe.qb.from_(pii
    ).join(pi
    ).on(pii.parent == pi.name
    ).select(
        pi.name.as_('purchase_invoice'),
        pi.supplier,
        pi.supplier_name,
        pi.posting_date.as_('pi_date'),
        pii.item_code,
        pii.item_name,
        Sum(pii.qty).as_('pi_qty'),
        Avg(pii.valuation_rate).as_('pi_rate'),
        Sum(pii.base_net_amount).as_('pi_item_amount')
    ).groupby(
        pi.supplier, pi.name, pii.item_code, pii.item_name
    ).where(
        (pii.valuation_rate>0) &    # 剔除非库存物料
        (pi.docstatus==1)
    )                  
    
    if pi_amount:    
        query = pi_query.where((pi.name.isin(list(pi_amount))))
        if suppliers:
            query = query.where(pi.supplier.isin(suppliers))
        #发票明细4种情况：同时有pr_detail与po_detail,分别只有pr_detail或po_detail,两者都没有
        pi_not_by_po = query.select(
            ConstantColumn("").as_("po_detail"),
            pii.pr_detail
        ).where(
            (
                (pii.pr_detail.notnull()) |
                (pii.pr_detail.isnull() & pii.po_detail.isnull())
            ) 
        ).groupby(pii.pr_detail
        ).run(as_dict=1)
        
        pi_by_po = query.select(
            ConstantColumn("").as_("pr_detail"),
            pii.po_detail
        ).where(
            (pii.po_detail.notnull()) & 
            (pii.pr_detail.isnull()) 
        ).groupby(pii.po_detail
        ).run(as_dict=1)
        data = pi_not_by_po + pi_by_po
        pr_detail_in_pi = {d.pr_detail for d in data if d.pr_detail}
        po_detail_in_pi = {d.po_detail for d in data if d.po_detail}
        for d in data:
            d.pi_amount = pi_amount.get(d.purchase_invoice)
    
    pr_query = frappe.qb.from_(pri
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
        Sum(pri.qty).as_('pr_qty'),
        Avg(pri.valuation_rate).as_('pr_rate'),
        Sum(pri.base_net_amount + pri.rate_difference_with_purchase_invoice).as_('pr_item_amount')
    ).groupby(
        pr.supplier, pr.status, pr.name, pri.idx, pri.item_code, pri.item_name
    ).where(        
        (pr.docstatus==1)
    )

    if pr_amount:
        query_filtered_pr = pr_query.where(
            (pri.valuation_rate>0) &
            (pr.name.isin(list(pr_amount)))
        )
        if suppliers:
            query_filtered_pr = query_filtered_pr.where(pr.supplier.isin(suppliers))
                    
        query_pr_detail = query_filtered_pr.select(pri.name.as_('pr_detail')).groupby(pri.name)
        if po_detail_in_pi:
            query_pr_detail = query_pr_detail.where(
                (
                    pri.purchase_order_item.notin(po_detail_in_pi) |
                    pri.purchase_order_item.isnull()
                )
            )
        pr_data = query_pr_detail.run(as_dict=1)
        pr_detail_dict = {d.pr_detail:d for d in pr_data}

        if po_detail_in_pi:
            query_po_detail = query_filtered_pr.select(pri.purchase_order_item.as_('po_detail')
            ).where(pri.purchase_order_item.isin(po_detail_in_pi)       #用发票是否以采购订单对账为准区分
            ).groupby(pri.purchase_order_item)
            pr_data_by_po_detail = query_po_detail.run(as_dict=1)
            po_detail_dict = {d.po_detail:d for d in pr_data_by_po_detail}

    fields = ['purchase_receipt', 'pr_date', 'pr_status','pr_item_idx', 'pr_qty','pr_rate','pr_item_amount']
    #发票匹配入库
    if pr_detail_dict or po_detail_dict:        
        for d in data:
            pr_detail = {}
            if not (d.pr_detail or d.po_detail):continue
            #用pop而不是get 处理出库明细多次开票场景，出库明细只匹配第一个发票明细行
            if d.pr_detail:
                pr_detail = pr_detail_dict.pop(d.pr_detail, {})
            if not pr_detail and d.po_detail:
                pr_detail = po_detail_dict.pop(d.po_detail,{})
            if pr_detail:
                for f in fields:
                    d[f] = pr_detail[f]
    
    #有入库无发票
    if pr_data or pr_data_by_po_detail:
        globals().update(locals())
        matched_pr = {d.purchase_receipt for d in data if d.purchase_receipt}
        data.extend([d for d in pr_data + pr_data_by_po_detail if 
            (d.pr_detail and d.pr_detail not in pr_detail_in_pi) or 
            (d.po_detail and d.po_detail not in po_detail_in_pi) or
            (not (d.po_detail or d.pr_detail) and d.purchase_receipt not in matched_pr)
        ])

    #扩展匹配，继续匹配有发票无入库以及有入库无发票的
    if extended_match:
        #处理发票对入库一对多问题，只匹配一次
        matched_pr_detail = {d.pr_detail for d in data if d.pr_detail}
        pr_detail_in_pi_no_pr = [d.pr_detail for d in data if d.purchase_invoice and d.pr_detail and not d.purchase_receipt
            and not d.pr_detail in matched_pr_detail
        ]
        matched_po_detail = {d.po_detail for d in data if d.po_detail}
        po_detail_in_pi_no_pr = [d.po_detail for d in data if d.purchase_invoice and d.po_detail and not d.purchase_receipt
            and not d.po_detail in matched_po_detail
        ]
        pr_detail_no_pi = [d.pr_detail for d in data if not d.purchase_invoice and d.purchase_receipt]
        if pr_detail_in_pi_no_pr or po_detail_in_pi_no_pr:
            if pr_detail_in_pi_no_pr:
                pr_data = pr_query.select(pri.name.as_('pr_detail')
                ).groupby(pri.name
                ).where(pri.name.isin(pr_detail_in_pi_no_pr)
                ).run(as_dict=1)
                #按采购入库汇总明细行金额                                
                for d in pr_data:
                    pr_amount.setdefault(d.purchase_receipt, 0)
                    pr_amount[d.purchase_receipt] += d.pr_item_amount
                pr_detail_dict = {d.pr_detail:d for d in pr_data}
            elif po_detail_in_pi_no_pr:
                pr_data = pr_query.select(pri.purchase_order_item.as_('po_detail')
                ).groupby(pri.purchase_order_item
                ).where(pri.purchase_order_item.isin(po_detail_in_pi_no_pr)
                ).run(as_dict=1)

                for d in pr_data:
                    pr_amount.setdefault(d.purchase_receipt, 0)
                    pr_amount[d.purchase_receipt] += d.pr_item_amount
                po_detail_dict = {d.po_detail:d for d in pr_data}

            #发票匹配入库        
            for d in data:
                if d.purchase_receipt:continue
                #按入库明细行与采购明细行匹配,用pop而不是get处理出库多次开发票场景，避免重复匹配
                if d.pr_detail or d.po_detail:
                    pr_detail = (pr_detail_dict.pop(d.pr_detail, {}) if d.pr_detail
                        else po_detail_dict.pop(d.po_detail, {}))
                    if pr_detail:
                        for f in fields:
                            d[f] = pr_detail[f]

        if pr_detail_no_pi:
            pi_query = pi_query.where(pii.pr_detail.isin(pr_detail_no_pi))
            pi_not_by_po = pi_query.select(
                ConstantColumn("").as_("po_detail"),
                pii.pr_detail
            ).where(
                (
                    (pii.pr_detail.notnull()) |
                    (pii.pr_detail.isnull() & pii.po_detail.isnull())
                ) 
            ).groupby(pii.pr_detail
            ).run(as_dict=1)
            
            pi_by_po = pi_query.select(
                ConstantColumn("").as_("pr_detail"),
                pii.po_detail
            ).where(
                (pii.po_detail.notnull()) & 
                (pii.pr_detail.isnull()) 
            ).groupby(pii.po_detail
            ).run(as_dict=1)
            pi_data = pi_not_by_po + pi_by_po               
            for d in pi_data:
                pi_amount.setdefault(d.purchase_invoice, 0)
                pi_amount[d.purchase_invoice] += d.pi_item_amount
            pi_detail_dict = {d.pr_detail:d for d in pi_data}

            #入库匹配发票
            for d in data:
                if not d.purchase_invoice:
                    pi_detail = pi_detail_dict.get(d.pr_detail)
                    if pi_detail:
                        for f in ['purchase_invoice', 'pi_date', 'pi_qty','pi_rate','pi_item_amount']:
                            d[f] = pi_detail[f]                        

    #计算差异
    df = frappe.get_meta("Purchase Invoice Item").get_field('amount')
    precision = get_field_precision(df)        
    for d in data:
        if d.purchase_receipt:
            d.pr_amount = pr_amount.get(d.purchase_receipt, 0)
        elif d.purchase_invoice:
            d.pi_amount = pi_amount.get(d.purchase_invoice, 0)        
        d.variance = flt(d.get('pi_item_amount', 0) - d.get('pr_item_amount', 0), precision)
        msg = ''

        if not d.purchase_receipt:
            msg = _('No purchase receipt')
        elif not d.purchase_invoice:
            msg = _('No purchase invoice')
        elif not d.pr_rate:            
            msg = _('PR valuation rate is 0')
        elif d.variance:
            msg = _('PR and PI not match')
        if msg: d.variance_reason = msg
    if filters.hide_fully_matched:
        data = [d for d in data if flt(d.variance, precision) != 0]

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
            "width": 90
        },
        {
            "label": _("PR Rate"),
            "fieldname": "pr_rate",
            "fieldtype": "Float",
            "width": 90
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
            "width": 150,
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
        {
            "label": _("Variance"), 
            "fieldname": "variance", 
            "fieldtype": "Currency", 
            "width": 100,
            "options": "Company:company:default_currency",
        },
        {
            "label": _("Variance Reason"), 
            "fieldname": "variance_reason", 
            "fieldtype": "Data", 
            "width": 130,
        }          
    ]


"""
for testing 
from frappe import _
from frappe.query_builder.functions import Sum, Avg
from erpnext.accounts.report.general_ledger.general_ledger import get_gl_entries,get_result
from zelin_ac.zelin_accounting.report.gr_ir_reconciliation.gr_ir_reconciliation import *
filters= frappe._dict(
    {"company":"则霖信息技术（深圳）有限公司",
    "from_date":"2024-01-1",
    "to_date":"2024-05-23",
    "account":["220202 - 应付账款-暂估库存 - 则"],
    "group_by":"Group by Voucher (Consolidated)",
    "extended_match":0,
    "hide_fully_matched":0}
)
"""