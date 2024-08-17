import click
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def make_custom_fields():
	if ("hrms" in frappe.get_installed_apps() and 
		not frappe.get_meta("Expense Claim Detail").has_field("invoice_recognition")):
		click.secho("* Installing zelin accounting add Custom Fields in Expense Claim Detail")

		create_custom_fields(
			{
				"Expense Claim Detail": [
					{
						"fieldname": "file_url",
						"fieldtype": "Data",
						"label": "File URL",
						"read_only":1,
						"allow_on_submit":1,
						"insert_after": "project",
					},
					{
						"fieldname": "invoice_recognition",
						"fieldtype": "Link",
						"label": "Invoice Recognition",
						"options":"Invoice Recognition",
						"read_only":1,
						"allow_on_submit":1,
						"in_list_view":1,
						"insert_after": "file_url",
					}
				]
			}
		)

		create_custom_fields(
			{
				"Expense Claim": [
					{
						"fieldname": "default_expense_type",
						"fieldtype": "Link",
						"label": "Default Expense Type",
						"options":"Expense Type",						
						"insert_after": "approval_status",
					},
					{
						"fieldname": "recognize_invoice",
						"fieldtype": "Button",
						"label": "Recognize Invoice",
						"depends_on": "eval:(!doc.__islocal && (!doc.expenses || doc.expenses.length===0))"					
						"insert_after": "expense_details",
					},					
					{
						"fieldname": "total_recognized_amount",
						"fieldtype": "Float",
						"label": "Total Recognized Amount",
						"depends_on": "eval:doc.total_recognized_amount",
						"read_only": 1,						
						"insert_after": "grand_total",
					}
				]
			}

			total_claimed_amount
		)
		make_property_setter("Expense Claim", "expenses", "reqd", 0, "Check", validate_fields_for_doctype=False)
		frappe.clear_cache(doctype="Expense Claim")

def delete_custom_fields():
	if frappe.get_meta("Expense Claim Detail").has_field("invoice_recognition"):
		click.secho("* Uninstalling zelin accounting  remove Custom Fields from Expense Claim Detail")

		fieldnames = (
			"recognize_invoice",
			"default_expense_type",
			"total_recognized_amount"
		)

		for fieldname in fieldnames:
			frappe.db.delete("Custom Field", {"name": "Expense Claim Detail-" + fieldname})

		fieldnames = (
			"invoice_recognition",
			"file_url"
		)

		for fieldname in fieldnames:
			frappe.db.delete("Custom Field", {"name": "Expense Claim Detail-" + fieldname})

		make_property_setter("Expense Claim", "expenses", "reqd", 1, "Check", validate_fields_for_doctype=False)
		frappe.clear_cache(doctype="Expense Claim Detail")
