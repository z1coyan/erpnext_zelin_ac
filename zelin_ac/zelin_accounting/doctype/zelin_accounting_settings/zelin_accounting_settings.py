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
	]
}

class ZelinAccountingSettings(Document):
	def on_update(self):
		before_save = self.get_doc_before_save()
		if (before_save and 
			before_save.disable_toggle_debit_credit_if_negative != self.disable_toggle_debit_credit_if_negative):
			frappe.cache().delete_value('disable_toggle_debit_credit_if_negative')

		if (not before_save or before_save.enable_stock_entry_movement_reason != self.enable_stock_entry_movement_reason):
			if self.enable_stock_entry_movement_reason:
				self.create_custom_fields(key='enable_stock_entry_movement_reason')
			else:
				self.remove_custom_fields(key='enable_stock_entry_movement_reason')

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