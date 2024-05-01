import frappe
from frappe import _

from frappe.model.meta import get_field_precision
from erpnext import get_default_currency    
from frappe.query_builder.functions import Coalesce, Round
from frappe.query_builder import Case
from pypika import Order    


def execute(filters=None):
    columns = get_column()
    data = get_ordered_to_be_billed_data(filters)
    return columns, data

def get_column():
    return [
        {
            "label": _("Delivery Note"),
            "fieldname": "delivery_note",
            "fieldtype": "Link",
            "options": "Delivery Note",
            "width": 160,
        },
        {
            "label": _("Customer's Purchase Order"),
            "fieldname": "po_no",
            "fieldtype": "Data",            
            "width": 120,
        },        
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 130},
        {
            "label": _("Customer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 120,
        },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 120},
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120,
        },
        {
            "label": _("Qty"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Rate"),
            "fieldname": "rate",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 100,
            "editable": True,
            "options": "Company:company:default_currency",
        },                
        {
            "label": _("Billed Amount"),
            "fieldname": "billed_amount",
            "fieldtype": "Currency",
            "width": 100,
            "options": "Company:company:default_currency",
        },
        {
            "label": _("Returned Amount"),
            "fieldname": "returned_amount",
            "fieldtype": "Currency",
            "width": 120,
            "options": "Company:company:default_currency",
        },
        {
            "label": _("Billable Amount"),
            "fieldname": "billable_amount",
            "fieldtype": "Currency",
            "width": 120,
            "options": "Company:company:default_currency",
        },
        # 报表添加自定义字段不支持子单据类型
        #{"label": _("Delivery Note Item"), "fieldname": "dn_detail", "fieldtype": "Link", "options":"Delivery Note Item", "hidden": 0},
        {"label": _("Customer's Item Code"), "fieldname": "customer_item_code", "fieldtype": "Data", "width": 120},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 120},
        {"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 120},
        {
            "label": _("Project"),
            "fieldname": "project",
            "fieldtype": "Link",
            "options": "Project",
            "width": 120,
        },
        {"label": _("Is Return"), "fieldname": "is_return", "fieldtype": "Check", "width": 60},
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 120,
        },
        {            
            "fieldname": "child_name",
            "fieldtype": "Data",
            "hidden": 1
        }
    ]

def get_ordered_to_be_billed_data(filters):
    """
    改为pypika
    name 改为delivery_note字段名
    加childname字段
    添加剔除草稿状态中的出库明细
    """

    precision = (
        get_field_precision(
            frappe.get_meta('Delivery Note Item').get_field("billed_amt"), currency=get_default_currency()
        )
        or 2
    )
    
    dn = frappe.qb.DocType('Delivery Note')
    dni = frappe.qb.DocType('Delivery Note Item')
    dni_meta = frappe.get_meta("Delivery Note Item")

    query = frappe.qb.from_(dn
    ).join(dni
    ).on(dn.name == dni.parent
    ).select(
        dn.name.as_('delivery_note'),
        dn.is_return,
        dn.posting_date,
        dn.customer,
        dn.customer_name,    
        #dni.name.as_("dn_detail"),
        dni.item_code,
        dni.customer_item_code,
        dni.qty,
        dni.rate,
        dni.base_amount.as_('amount'),
        (dni.billed_amt * Coalesce(dn.conversion_rate, 1)).as_('billed_amount'),
        (dni.base_rate * Coalesce(dni.returned_qty, 0)).as_('returned_amount'),
        (dni.base_amount -
            (dni.billed_amt * Coalesce(dn.conversion_rate, 1)) -
            (dni.base_rate * Coalesce(dni.returned_qty, 0))).as_('billable_amount'),
        dni.item_name, 
        dni.description,
        dn.project,
        dn.company,
        dni.name.as_('child_name')
    ).where(
        (dn.company==filters.get('company')) &
        (dn.posting_date.between(filters.get('from_date'), filters.get('to_date'))) &
        (dn.docstatus == 1) &
        (dn.status.notin(['Closed', 'Completed'])) &
        #(dni.amount > 0) &
        Case(            
        ).when(
            dn.is_return == 0,
            (dni.base_amount -
                Round(dni.billed_amt * Coalesce(dn.conversion_rate, 1), precision) -
                (dni.base_rate * Coalesce(dni.returned_qty, 0)) > 0
            )
        ).else_(
            (dni.base_amount - Round(dni.billed_amt * Coalesce(dn.conversion_rate, 1), precision) < 0
            )
        )
    ).orderby(dn.name, Order.desc)

    if dni_meta.has_field('po_no'):
        query = query.select(dni.po_no)
    else:
        query = query.select(dn.po_no)

    delivery_category = filters.delivery_category
    if delivery_category:
        is_return = delivery_category == 'Return Delivery'
        query = query.where(dn.is_return == is_return)

    customer = filters.get('customer')
    if customer:
        query = query.where(dn.customer==customer)

    po_no = filters.get('po_no')
    if po_no:
        if dni_meta.has_field('po_no'):
            query = query.where(dni.po_no.isin(po_no.split('\n')))
        else:
            query = query.where(dn.po_no.isin(po_no.split('\n')))
    exclude_in_draft_invoice = filters.get('exclude_in_draft_invoice')
    if exclude_in_draft_invoice:
        sii = frappe.qb.DocType('Sales Invoice Item')
        query = query.left_join(sii
        ).on((sii.dn_detail == dni.name) & 
            (sii.docstatus == 0) 
        ).where(sii.name.isnull())
    return query.run(as_dict=1)


"""
for test
filters = {"company":"则霖信息技术（深圳）有限公司","from_date":"2024-03-30","to_date":"2024-04-30","po_no":"4502\n4501\n4503","exclude_in_draft_invoice":1}
from zelin_ac.zelin_accounting.report.delivery_notes_to_bill.delivery_notes_to_bill import *


"""