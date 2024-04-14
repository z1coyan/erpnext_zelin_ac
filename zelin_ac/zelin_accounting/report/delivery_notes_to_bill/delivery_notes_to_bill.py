import frappe
from frappe import _

from frappe.model.meta import get_field_precision
from erpnext import get_default_currency    
from frappe.query_builder.functions import Coalesce, Round
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
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 130},
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
			"label": _("Pending Amount"),
			"fieldname": "pending_amount",
			"fieldtype": "Currency",
			"width": 120,
			"options": "Company:company:default_currency",
		},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 120},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 120},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 120,
		},
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

    query = frappe.qb.from_(dn
    ).join(dni
    ).on(dn.name == dni.parent
    ).select(
        dn.name.as_('delivery_note'),
        dn.posting_date,
        dn.customer,
        dn.customer_name,
        dni.item_code,
        dni.base_amount,
        (dni.billed_amt * Coalesce(dn.conversion_rate, 1)),
        (dni.base_rate * Coalesce(dni.returned_qty, 0)),
        (dni.base_amount -
            (dni.billed_amt * Coalesce(dn.conversion_rate, 1)) -
            (dni.base_rate * Coalesce(dni.returned_qty, 0))),
        dni.item_name, dni.description,
        dn.project,
        dn.company,
        dni.name.as_('child_name')
    ).where(
        (dn.company==filters.get('company')) &
        (dn.posting_date.between(filters.get('from_date'), filters.get('to_date'))) &
        (dn.docstatus == 1) &
        (dn.status.notin(['Closed', 'Completed'])) &
        (dni.amount > 0) &
        (dni.base_amount -
            Round(dni.billed_amt * Coalesce(dn.conversion_rate, 1), precision) -
            (dni.base_rate * Coalesce(dni.returned_qty, 0))) > 0
    ).orderby(dn.name, Order.desc)
    customer = filters.get('customer')
    if customer:
        query = query.where(dn.customer==customer)
    exclude_in_draft_invoice = filters.get('exclude_in_draft_invoice')
    if exclude_in_draft_invoice:
        sii = frappe.qb.DocType('Sales Invoice Item')
        query = query.left_join(sii
        ).on((sii.dn_detail == dni.name) & 
            (sii.docstatus == 0) 
        ).where(sii.name.isnull())

    return query.run()
