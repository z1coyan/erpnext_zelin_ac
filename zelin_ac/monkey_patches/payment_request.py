import frappe
from frappe.utils import flt
from erpnext.accounts.doctype.payment_request import payment_request

def custom_get_existing_payment_request_amount(ref_dt, ref_dn):
	"""
    fisher
    前面的payment request状态为已付款，还可以再下推付款申请
	此代码去掉了where条件中的 and (status != 'Paid'
	"""
	existing_payment_request_amount = frappe.db.sql(
		"""
		select sum(grand_total)
		from `tabPayment Request`
		where
			reference_doctype = %s
			and reference_name = %s
			and docstatus = 1
	""",
		(ref_dt, ref_dn),
	)
	return flt(existing_payment_request_amount[0][0]) if existing_payment_request_amount else 0

payment_request.get_existing_payment_request_amount = custom_get_existing_payment_request_amount