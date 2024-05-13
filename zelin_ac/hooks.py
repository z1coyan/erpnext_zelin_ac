from . import __version__ as app_version

app_name = "zelin_ac"
app_title = "Zelin Accounting"
app_publisher = "Vnimy"
app_description = "Zelin Accounting"
app_email = "vnimy@mediad.cn"
app_license = "MIT"

fixtures = [
    {
        "doctype": "Month End Tracking",
        "filters": [
        ]
    }
]

doctype_list_js = {
	"Delivery Note" : "public/js/delivery_note.js"	
}

doctype_js = {
	"Stock Entry" : "public/js/stock_entry.js",
	"Material Request" : "public/js/material_request.js",
	"Account" : "public/js/account.js",
	"Sales Invoice" : "public/js/sales_invoice.js",
}

doc_events = {
 	"Stock Entry": {
 		"validate": "zelin_ac.doc_events.stock_entry_validate"
	},
	"Subcontracting Receipt": {
 		"validate": "zelin_ac.doc_events.subcontracting_receipt_validate"
	},
	"Delivery Note": {
 		"on_submit": "zelin_ac.doc_events.process_return_doc_status",
		"on_cancel": "zelin_ac.doc_events.process_return_doc_status"
	},
	"Purchase Receipt": {
 		"on_submit": "zelin_ac.doc_events.process_return_doc_status",
		"on_cancel": "zelin_ac.doc_events.process_return_doc_status"
	},
	"Sales Order": {
 		"before_print": "zelin_ac.doc_events.sales_order_before_print"
	},
}

override_doctype_class = {
	"Purchase Invoice": "zelin_ac.overrides.CustomPurchaseInvoice",
	"Sales Invoice": "zelin_ac.overrides.CustomSalesInvoice"
}

override_whitelisted_methods = {
	"frappe.utils.print_format.download_multi_pdf_async": "zelin_ac.overrides.custom_download_multi_pdf_async",
	"erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry": "zelin_ac.overrides.get_payment_entry"
}