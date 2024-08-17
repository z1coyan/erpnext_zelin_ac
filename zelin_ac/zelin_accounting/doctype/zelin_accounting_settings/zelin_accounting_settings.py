# Copyright (c) 2024, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

custom_fields = {
	'enable_stock_entry_movement_reason': [
		{
			"doctype": "Custom Field",
			"dt": "Material Request",
			"fieldname": "reason_code",
			"fieldtype": "Link",
			"options":"Material Move Reason Code",
			"insert_after": "schedule_date",
			"label": "Material Move Reason Code",
			"depends_on": "eval:doc.material_request_type ==='Material Issue'",    
			"modified": "2024-03-25 22:12:02.049024",
			"name": "Material Request-reason_code"
		},
		{
			"doctype": "Custom Field",
			"dt": "Stock Entry",
			"fieldname": "reason_code",
			"fieldtype": "Link",
			"options":"Material Move Reason Code",
			"insert_after": "stock_entry_type",
			"label": "Material Move Reason Code",
			"depends_on": "eval:in_list(['Material Issue','Material Receipt'], doc.stock_entry_type)", 
			"mandatory_depends_on": "eval:in_list(['Material Issue','Material Receipt'], doc.stock_entry_type)",
			"modified": "2024-3-25 22:12:02.049025",
			"name": "Stock Entry-reason_code"
		},
		{
			"doctype": "Custom Field",
			"dt": "Stock Entry",
			"fieldname": "expense_account",
			"fieldtype": "Link",
			"options":"Account",
			"insert_after": "reason_code",
			"label": "Expense Account",
			"depends_on": "eval:doc.reason_code",    
			"modified": "2023-12-10 22:12:02.049023",
			"name": "Stock Entry-expense_account"
		}
	],
	'enable_rate_include_tax': [
		{
			"doctype": "Custom Field",
			"dt": "Sales Order Item",
			"fieldname": "custom_rate_include_tax",
			"fieldtype": "Float",
			"hidden": 1,
			"read_only": 1,
			"insert_after": "rate",
			"label": "Rate Include Tax",			
			"modified": "2024-05-13 22:12:02.049024",
			"name": "Sales Order Item-custom_rate_include_tax"
		},
		{
			"doctype": "Custom Field",
			"dt": "Sales Order Item",
			"fieldname": "custom_amount_include_tax",
			"fieldtype": "Float",
			"hidden": 1,
			"read_only": 1,
			"insert_after": "custom_rate_include_tax",
			"label": "Amount Include Tax",			
			"modified": "2024-05-13 22:12:02.049024",
			"name": "Sales Order Item-custom_amount_include_tax"
		}
	],
	'enable_dni_billed_qty': [
		{
			"doctype": "Custom Field",
			"dt": "Delivery Note Item",
			"fieldname": "custom_billed_qty",
			"fieldtype": "Float",
			"read_only": 1,
			"insert_after": "base_net_amount",
			"label": "Billed Qty",			
			"modified": "2024-05-14 22:12:02.049024",
			"name": "Delivery Note Item-custom_billed_qty"
		}
	],
	'enable_scale_price':[		
   		{
			"doctype": "Custom Field",
			"dt": "Item Price",
			"fieldname": "sb_scale_price",
			"fieldtype": "Section Break",
			"collapsible": 1,
			"insert_after": "price_list_rate",
			"modified": "2024-05-17 22:18:02.049025",
			"name": "Item Price-sb_scale_price"
		},
		{
			"doctype": "Custom Field",
			"dt": "Item Price",
			"fieldname": "scale_prices",
			"label": "Scale Prices",
			"fieldtype": "Table",
			"allow_bulk_edit": 1,
			"options": "Item Price Scale Price",
			"insert_after": "sb_scale_price",
			"modified": "2024-05-17 22:18:02.049025",
			"name": "Item Price-scale_prices"
		}
	],
	'enable_purchase_invoice_variance_settlement':[
		{
			"doctype": "Custom Field",
			"dt": "Stock Entry",
			"fieldname": "purchase_invoice",
			"label": "Purchase Invoice",
			"fieldtype": "Link",
			"read_only": 1,
			"options": "Purchase Invoice",
			"insert_after": "sales_invoice_no",
			"depends_on": "eval:doc.purpose=='Repack'",
			"modified": "2024-05-19 22:18:02.049025",
			"name": "Stock Entry-purchase_invoice"
		},
		{
			"doctype": "Custom Field",
			"dt": "Stock Entry Detail",
			"fieldname": "flagged_additional_cost",
			"label": "flagged_additional_cost",
			"fieldtype": "Float",
			"read_only": 1,
			"hidden": 1,
			"insert_after": "additional_cost",
			"modified": "2024-05-19 22:18:02.049025",
			"name": "Stock Entry Detail-flagged_additional_cost"
		}
	],
	'enable_debug_repost_item_valuation':[
		{
			"doctype": "Custom Field",
			"dt": "Repost Item Valuation",
			"fieldname": "custom_items_to_be_repost",
			"fieldtype": "Code",
			"insert_after": "affected_transactions",
			"depends_on": "eval:frappe.session.user == 'Administrator' || frappe.user.has_role('System Manager')",
			"label": "Items to Be Repost",
			"no_copy": 1,
			"print_hide": 1,
			"read_only": 1,
			"modified": "2024-07-18 22:18:02.049025",
			"name": "Repost Item Valuation-custom_items_to_be_repost"
		},
		{
			"doctype": "Custom Field",
			"dt": "Repost Item Valuation",
			"fieldname": "custom_distinct_item_and_warehouse",
			"fieldtype": "Code",
			"insert_after": "custom_items_to_be_repost",
			"depends_on": "eval:frappe.session.user == 'Administrator' || frappe.user.has_role('System Manager')",
			"label": "Distinct Item and Warehouse",
			"no_copy": 1,
			"print_hide": 1,
			"read_only": 1,
			"modified": "2024-07-18 22:18:02.049025",
			"name": "Repost Item Valuation-custom_distinct_item_and_warehouse"
		},		
		{
			"doctype": "Custom Field",
			"dt": "Repost Item Valuation",
			"fieldname": "custom_affected_transactions",
			"fieldtype": "Code",
			"insert_after": "custom_distinct_item_and_warehouse",
			"depends_on": "eval:frappe.session.user == 'Administrator' || frappe.user.has_role('System Manager')",
			"label": "Affected Transactions",
			"no_copy": 1,
			"read_only": 1,
			"modified": "2024-07-18 22:18:02.049025",
			"name": "Repost Item Valuation-custom_affected_transactions"
		}
	]

}

class ZelinAccountingSettings(Document):
	def on_update(self):
		before_save = self.get_doc_before_save()
		for key in custom_fields.keys():
			#标准结转采购入库未考虑账期关闭问题，需停掉
			if key == 'enable_purchase_invoice_variance_settlement' and self.get(key):
				frappe.db.set_single_value("Buying Settings",
					"set_landed_cost_based_on_purchase_invoice_rate", 0)
			if (not before_save or before_save.get(key) != self.get(key)):
				frappe.cache().delete_value(key)
				if self.get(key):
					self.create_custom_fields(key)
				else:
					self.remove_custom_fields(key)		

	def create_custom_fields(self, key):
		fields = custom_fields.get(key) or []
		for df in fields:
			if not frappe.db.exists('Custom Field', df.get('name')):
				create_custom_field(df.get('dt'), df, ignore_validate=True)

	def remove_custom_fields(self, key):
		fields = custom_fields.get(key) or []
		for df in fields:
			if frappe.db.exists('Custom Field', df.get('name')):
				frappe.delete_doc("Custom Field", df.get('name'))