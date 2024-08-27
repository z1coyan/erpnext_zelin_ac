# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class InvoiceReconciliation(Document):
    def on_submit(self):
        self.update_my_invoice_status('已核销')

    def on_cancel(self):
        self.update_my_invoice_status('已使用')

    def update_my_invoice_status(self, status):
        invoices = [r.invoice_name for r in self.items]
        frappe.db.set_value('My Invoice', {'name': ('in', invoices)}, 'status', status)


@frappe.whitelist()
def get_paid_invoice(start_date, end_date):
    status = "已使用"
    results = frappe.db.sql("""
        SELECT
            mi.name as invoice_name,
            mi.invoice_type as invoice_type,
            mi.net_amount as net_amount,
            mi.tax_amount as tax_amount,
            mi.amount as amount,
            mi.invoice_code as invoice_code,
            mi.description as description,
            mi.files as files,
            mi.expense_claim as expense_claim,
            mi.expense_claim_item as expense_claim_item,
            mi.owner_user as owner_user
        FROM
            `tabMy Invoice` AS mi
        LEFT JOIN `tabExpense Claim` AS ec ON ec.name = mi.expense_claim
        WHERE
            ec.paid_time between %s AND %s
        AND mi.status = %s
        """, (start_date, end_date, status))
    return results