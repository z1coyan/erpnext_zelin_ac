from . import __version__ as app_version

app_name = "zelin_ac"
app_title = "Zelin Accounting"
app_publisher = "Vnimy"
app_description = "Zelin Accounting"
app_email = "vnimy@mediad.cn"
app_license = "MIT"

fixtures = [
    {
        "doctype": "Cash Flow Code",
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
	}
}

override_doctype_class = {
	"Purchase Invoice": "zelin_ac.overrides.CustomPurchaseInvoice",
	"Sales Invoice": "zelin_ac.overrides.CustomSalesInvoice"
}