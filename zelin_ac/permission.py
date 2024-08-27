import frappe


def is_special_user(user):
    roles = frappe.get_roles(user)
    exclude_roles = ["System Manager", "Accounts User", "Accounts Manager"]
    special_user = any(r in exclude_roles for r in roles) or (user =="Administrator")
    return bool(special_user)

def my_invoice_query_conditions(user):
    conditions = ""
    user = user or frappe.session.user
    if not is_special_user(user):
        conditions = 'owner_user="%s" ' %(user)  
    return conditions

def my_invoice_has_permission(doc, ptype="read", user=None):
    pass