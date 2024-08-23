import click
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


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
			"tax_amount",
			"invoice_num",
			"file_url"
		)

		for fieldname in fieldnames:
			frappe.db.delete("Custom Field", {"name": "Expense Claim Detail-" + fieldname})

		make_property_setter("Expense Claim", "expenses", "reqd", 1, "Check", validate_fields_for_doctype=False)
		frappe.clear_cache(doctype="Expense Claim Detail")
