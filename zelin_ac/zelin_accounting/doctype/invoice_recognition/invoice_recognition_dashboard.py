from frappe import _


def get_data():
	return {
		"fieldname": "invoice_recognition",
		"transactions": [
			{"label": _("Expense Claim"), "items": ["Expense Claim"]},
		],
	}