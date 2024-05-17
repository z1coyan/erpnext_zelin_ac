import frappe
from frappe.model.document import Document
from frappe.www.printview import get_rendered_template
from frappe.www import printview


def custom_get_rendered_template(
    doc: "Document",
	print_format: str | None = None,
	meta=None,
	no_letterhead: bool | None = None,
	letterhead: str | None = None,
	trigger_print: bool = False,
	settings=None,
):
    track_print = frappe.db.get_single_value('Zelin Accounting Settings', 'track_print')
    if track_print:                   
        frappe.get_doc({
            'doctype':"Print Log",
            'reference_doctype': doc.doctype,
            'reference_name': doc.name,
            'print_format': print_format.name if isinstance(print_format, Document) else print_format
        }).insert(ignore_permissions=1)
        frappe.db.commit()
    html = get_rendered_template(
        doc,
        print_format=print_format,
        meta=meta,
        no_letterhead=no_letterhead,
        letterhead=letterhead,
        trigger_print=trigger_print,
        settings=settings,
    )
    return html
    
printview.get_rendered_template = custom_get_rendered_template