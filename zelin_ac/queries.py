import frappe
from zelin_ac.zelin_accounting.report.delivery_notes_to_bill.delivery_notes_to_bill import (
    get_ordered_to_be_billed_data)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_delivery_notes_to_be_billed(doctype, txt, searchfield, start, page_len, filters, as_dict):
    data = get_ordered_to_be_billed_data(filters)
    return data
