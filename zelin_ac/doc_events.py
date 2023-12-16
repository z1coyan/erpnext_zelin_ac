import frappe


def stock_entry_validate(doc, method):
    if doc.stock_entry_type == 'Material Issue' and doc.reason_code:
        expense_account = doc.expense_account
        if not expense_account:
            expense_account = frappe.db.get_value('Material Issue Default Account',
                {'company': doc.company,
                 'parent': doc.reason_code
                },
                'expense_account'
            )
        if expense_account:
            for row in doc.items:
                row.expense_account = expense_account