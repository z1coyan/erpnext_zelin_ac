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

#after_install = "zelin_ac.install.make_custom_fields"
#会出现本app单据类型尚未创建就执行了after_install代码，引用未创建的单据出错
#改用fixtures/custom_field.json机制
before_uninstall = "zelin_ac.install.delete_custom_fields"

doctype_list_js = {
	"Delivery Note" : "public/js/delivery_note.js"	
}

doctype_js = {
	"Stock Entry" : "public/js/stock_entry.js",
	"Item Price" : "public/js/item_price.js",
	"Material Request" : "public/js/material_request.js",
	"Account" : "public/js/account.js",
	"Sales Invoice" : "public/js/sales_invoice.js",
	"Expense Claim" : "public/js/expense_claim.js",
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
	"Purchase Invoice": {
 		"on_submit": "zelin_ac.doc_events.purchase_invoice_submit",
		"on_cancel": "zelin_ac.doc_events.purchase_invoice_cancel"
	},
	"Sales Order": {
 		"before_print": "zelin_ac.doc_events.sales_order_before_print"
	},
	"Item Price": {
 		"validate": "zelin_ac.doc_events.item_price_validate"
	},
	"File": {
 		"after_insert": "zelin_ac.doc_events.file_after_insert",
		"on_trash": "zelin_ac.doc_events.file_on_trash"

	},
	"Expense Claim": {
		"on_submit": [
			"zelin_ac.doc_events.validate_invoice_status",
			],
		"on_cancel": [
			"zelin_ac.doc_events.validate_invoice_status",
			],
		"before_submit":"zelin_ac.doc_events.expense_claim_before_submit",
	},
}

override_doctype_class = {
	"Purchase Invoice": "zelin_ac.overrides.CustomPurchaseInvoice",
	"Stock Entry": "zelin_ac.overrides.CustomStockEntry",
	"Delivery Note": "zelin_ac.overrides.CustomDeliveryNote",
	"Sales Invoice": "zelin_ac.overrides.CustomSalesInvoice"
}

override_whitelisted_methods = {
	"frappe.utils.print_format.download_multi_pdf_async": "zelin_ac.overrides.custom_download_multi_pdf_async",
	"frappe.www.printview.get_html_and_style": "zelin_ac.overrides.custom_get_html_and_style",
	"frappe.utils.print_format.download_pdf": "zelin_ac.overrides.custom_download_pdf",
	"erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry": "zelin_ac.overrides.get_payment_entry"
}

permission_query_conditions = {
	"Print Log": "zelin_ac.zelin_accounting.doctype.print_log.print_log.get_permission_query_conditions",
}

has_permission = {
	"Print Log": "zelin_ac.zelin_accounting.doctype.print_log.print_log.has_permission",
}