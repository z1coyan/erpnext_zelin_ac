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
			"insert_after": "reference",
			"modified": "2024-05-16 22:18:02.049025",
			"name": "Item Price-sb_scale_price"
		},
		{
			"doctype": "Custom Field",
			"dt": "Item Price",
			"fieldname": "scale_prices",
			"label": "Scale Prices",
			"fieldtype": "Table",
			"options": "Item Price Scale Price",
			"insert_after": "sb_scale_price",
			"modified": "2024-05-16 22:18:02.049025",
			"name": "Item Price-scale_prices"
		}
	]
}

class ZelinAccountingSettings(Document):
	def on_update(self):
		before_save = self.get_doc_before_save()
		for key in custom_fields.keys():
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