import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


def custom_validate_allocated_amount(self):
    if self.payment_type == "Internal Transfer":
        return

    if self.party_type in ("Customer", "Supplier"):
        self.validate_allocated_amount_with_latest_data()
    else:
        fail_message = _("Row #{0}: Allocated Amount cannot be greater than outstanding amount.")
        for d in self.get("references"):
            # flt加精度参数，以避免像142.73已分配金额(内部值可能是142.73000000001)，报错分配金额不能大于未付金额
            if (flt(d.allocated_amount)) > 0 and flt(d.allocated_amount, 3) > flt(d.outstanding_amount, 3):
                frappe.throw(fail_message.format(d.idx))

            # Check for negative outstanding invoices as well
            if flt(d.allocated_amount) < 0 and flt(d.allocated_amount) < flt(d.outstanding_amount):
                frappe.throw(fail_message.format(d.idx))

PaymentEntry.validate_allocated_amount = custom_validate_allocated_amount