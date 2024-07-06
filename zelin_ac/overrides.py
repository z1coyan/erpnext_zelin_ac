from datetime import datetime, timedelta
import frappe
import json
from frappe import _
from frappe.utils import flt
from frappe.query_builder.functions import Sum, Now
from frappe.query_builder import Interval
from frappe.www.printview import get_html_and_style as original_get_html_and_style
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from erpnext.stock.doctype.delivery_note.delivery_note import update_billed_amount_based_on_so
from erpnext.accounts.general_ledger import get_round_off_account_and_cost_center
from zelin_ac.api import get_cached_value


class CustomPaymentEntry(PaymentEntry):
	def validate_allocated_amount(self):
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

class CustomPurchaseInvoice(PurchaseInvoice):
    def get_gl_entries(self, warehouse_account=None):
        """
        在系统自动计算的税额与税票税额有差异时，允许手工输入实际税额，
        此代码将系统基于标准税额生成的总帐凭证税科目分录调整为手工税额
        将税额差异调至公司主数据中的圆整差异科目
        """

        gl_entries = super(CustomPurchaseInvoice, self).get_gl_entries(warehouse_account = warehouse_account)
        add_tax_adjust_gl_entries(self, gl_entries)
        return gl_entries

class CustomStockEntry(StockEntry):
    def distribute_additional_costs(self):
        """
        以代码在明细行直接分派的费用为准，不再用标准按金额分摊覆盖
        """

        additional_costs = sum(flt(t.base_amount) for t in self.get("additional_costs") or [])
        if additional_costs:
            item_additional_costs = sum(flt(t.additional_cost) for t in self.get("items") if t.t_warehouse)
            if flt(additional_costs - item_additional_costs, 4):
                super().distribute_additional_costs()

class CustomDeliveryNote(DeliveryNote):
    def validate_internal_transfer(self):
        if not self.doctype in ("Delivery Note"):
            super().validate_internal_transfer()

class CustomSalesInvoice(SalesInvoice):
    def validate_delivery_note(self):
        if any(row.dn_detail for row in self.items if row.dn_detail):
            dni = frappe.qb.DocType('Delivery Note Item')
            target_wh_map = frappe._dict(frappe.qb.from_(dni
            ).select(dni.name, dni.target_warehouse
            ).where(
                (dni.name.isin({row.dn_detail for row in self.items if row.dn_detail})) &
                (dni.target_warehouse.notnull())
            ).run())
            if target_wh_map:
                for row in self.items:
                    row.warehouse = target_wh_map.get(row.dn_detail) or row.warehouse
            else:
                super().validate_delivery_note()

    def get_gl_entries(self, warehouse_account=None):
        gl_entries = super(CustomSalesInvoice, self).get_gl_entries(warehouse_account = warehouse_account)
        add_tax_adjust_gl_entries(self, gl_entries)
        return gl_entries

    def validate_qty(self):
        """
        允许正常出库与退货在一张发票中，即跳过标准的明细行是否允许负数与表头退货勾选一致性检查
        """

        names_changed = set() 
        if not self.is_return:
            for row in self.items:
                if row.qty < 0:
                    row.qty *= -1
                    names_changed.add(row.name)

        super().validate_qty()

        if names_changed:
            for row in self.items:
                if row.name in names_changed:
                    row.qty *= -1

    def update_billing_status_in_dn(self , update_modified=True):
        """
            开票金额修正为出库单价*开票数量，实现基于开票数量更新出库单开票状态
        """

        if not get_cached_value('enable_dni_billed_qty'):
            super().update_billing_status_in_dn(update_modified=update_modified)
        else:
            updated_delivery_notes = []
            dn_detail_wise_data = {}
            dn_details = {row.dn_detail for row in self.items}
            if dn_details:
                sii = frappe.qb.DocType('Sales Invoice Item')
                dni = frappe.qb.DocType('Delivery Note Item')

                data = frappe.qb.from_(sii
                ).join(dni
                ).on(sii.dn_detail == dni.name
                ).select(
                    sii.dn_detail,
                    Sum(dni.rate*sii.qty).as_('billed_amt'),
                    Sum(sii.qty).as_('billed_qty'),
                ).where(
                    (dni.name.isin(dn_details)) &
                    (sii.docstatus==1)
                ).groupby(sii.dn_detail
                ).run(as_dict=1)
                dn_detail_wise_data = {row.dn_detail:row for row in data}

            for row in self.items:
                if row.dn_detail:
                    dn_detail_dict = dn_detail_wise_data.get(row.dn_detail, {})
                    if dn_detail_dict:
                        billed_amt, billed_qty = dn_detail_dict.billed_amt, dn_detail_dict.billed_qty
                    else:
                        billed_amt, billed_qty = 0, 0
                    frappe.db.set_value("Delivery Note Item", row.dn_detail, 
                        {
                            "billed_amt": billed_amt,
                            "custom_billed_qty": billed_qty
                        },
                        update_modified=update_modified
                    )                    
                    updated_delivery_notes.append(row.delivery_note)
                elif row.so_detail :
                    updated_delivery_notes += update_billed_amount_based_on_so(row.so_detail, update_modified)

            for dn in set(updated_delivery_notes):
                if dn:
                    frappe.get_doc("Delivery Note", dn).update_billing_percentage(update_modified=update_modified)

def add_tax_adjust_gl_entries(doc, gl_entries):
        
        tax_amount_map = {} #按税科目小计手工输入的实际税额
        total_adjust_amount = 0
        for row in doc.taxes:
            if row.charge_type != 'Actual' and row.actual_tax_amount and flt(row.actual_tax_amount - row.tax_amount):
                tax_account = row.account_head                
                tax_amount_map.setdefault(tax_account, 0)
                tax_amount_map[tax_account] += row.actual_tax_amount

        if tax_amount_map:
            for (tax_account, actual_tax_amount) in tax_amount_map.items():
                for row in gl_entries:
                    if row.account == tax_account:
                        if row.debit:
                            row.debit = actual_tax_amount
                            row.debit_in_account_currency = actual_tax_amount
                            total_adjust_amount +=  actual_tax_amount - row.debit
                        else:
                            row.credit = actual_tax_amount
                            row.credit_in_account_currency = actual_tax_amount
                            total_adjust_amount += actual_tax_amount - row.credit
                        break            
            add_adjust_gl_entry(doc, gl_entries, total_adjust_amount * -1)
                    
        return gl_entries

def add_adjust_gl_entry(doc, gl_entries, adjust_amount):
    """"""
    round_off_account, round_off_cost_center = get_round_off_account_and_cost_center(
        doc.company, "Purchase Invoice", doc.name, doc.use_company_roundoff_cost_center
    )
    has_round_off_account = False
    for row in gl_entries:
        if row.account == round_off_account:
            if row.debit:
                row.debit += adjust_amount
                row.debit_in_account_currency += adjust_amount                
            else:
                row.credit += adjust_amount                            
                row.credit_in_account_currency += adjust_amount                
            has_round_off_account = True
            break
    if not has_round_off_account:
        gl_entries.append(
            doc.get_gl_dict(
                {
                    "account": round_off_account,
                    "against": None,
                    "debit_in_account_currency": adjust_amount,
                    "debit": adjust_amount,
                    "cost_center": round_off_cost_center
                    if doc.use_company_roundoff_cost_center
                    else (doc.cost_center or round_off_cost_center),
                }            
            )
        )

@frappe.whitelist()
def custom_download_multi_pdf_async(
    doctype: str | dict[str, list[str]],
    name: str | list[str],
    format: str | None = None,
    no_letterhead: bool = False,
    letterhead: str | None = None,
    options: str | None = None,
):
    import json
    from frappe.utils.print_format import download_multi_pdf_async as original_download_multi_pdf_async

    # 每个原始凭证（源单据）生成多行总帐凭证，只用其中一个总帐凭证打印该原始凭证的多行总帐凭证
    if isinstance(doctype, str) and doctype == 'GL Entry':
        data = frappe.get_all('GL Entry', 
            filters={
                'name': ('in', json.loads(name))
            },
            fields = ['name', 'voucher_type', 'voucher_no']
        )
        keys = set()
        new_names = []
        for d in data:
            key = (d.voucher_type, d.voucher_no)
            if not key in keys:
                new_names.append(d.name)
                keys.add(key)
        name = json.dumps(new_names)

    return original_download_multi_pdf_async(
        doctype=doctype,
        name=name,
        format=format,
        no_letterhead=no_letterhead,
        options=options
    )

def create_print_log(doctype, docname, print_format):
    #当前会话同一个打印只创建一次打印日志
    if get_cached_value('track_print'):
        print_log = frappe.qb.DocType('Print Log')
        frappe.get_doc({
            'doctype':"Print Log",
            'reference_doctype': doctype,
            'reference_name': docname,
            'print_format': print_format
        }).insert(ignore_permissions=1)

@frappe.whitelist(allow_guest=True)
def custom_download_pdf(doctype, name, format=None, doc=None, no_letterhead=0, language=None, letterhead=None):
    from frappe.utils.print_format import download_pdf as original_download_pdf

    pdf = original_download_pdf(doctype, name, 
        format=format, doc=doc, no_letterhead=no_letterhead, language=language, letterhead=letterhead)
    document = doc or frappe.get_doc(doctype, name)
    create_print_log(document.doctype, document.name, format)
    return pdf

@frappe.whitelist()
def custom_get_html_and_style(
    doc: str | None = None,
    name: str | None = None,
    print_format: str | None = None,
    no_letterhead: bool | None = None,
    letterhead: str | None = None,
    trigger_print: bool = False,
    style: str | None = None,
    settings: str | None = None,
):
    if not doc: return
    html = original_get_html_and_style(
        doc = doc,
        name = name,
        print_format = print_format,
        no_letterhead = no_letterhead,
        letterhead = letterhead,
        trigger_print = trigger_print,
        style = style,
        settings = settings,
    )
    if isinstance(name, str):
        document = frappe.get_doc(doc, name)
    else:
        document = frappe.get_doc(json.loads(doc))
    if html:
        create_print_log(document.doctype, document.name, print_format)
    return html

@frappe.whitelist()
def get_payment_entry(
    dt,
    dn,
    party_amount=None,
    bank_account=None,
    bank_amount=None,
    party_type=None,
    payment_type=None,
    reference_date=None,
):
    """
        销售订单与采购订单下推付款时默认付款金额基于预付百分比(付款条款明细中到期日小于等于当天）而非整个订单金额
    """

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry as original_get_payment_entry

    pe = original_get_payment_entry(
        dt=dt,
        dn=dn,
        party_amount=party_amount,
        bank_account=bank_account,
        bank_amount=bank_amount,
        party_type=party_type,
        payment_type=payment_type,
        reference_date=reference_date,
    )
    if dt in  ('Sales Order', 'Purchase Order'):
        doc = frappe.get_doc(dt, dn)
        if doc.payment_schedule and doc.payment_schedule[0].due_date <= doc.transaction_date:
            field = 'payment_amount' if pe.paid_to_account_currency == doc.currency else 'base_payment_amount'
            adv_amount = doc.payment_schedule[0].get(field)
            if pe.paid_amount > adv_amount:
                pe.paid_amount = adv_amount                
                pe.references = pe.references[:1]
                pe.references[0].allocated_amount = adv_amount
                pe.set_amounts()
    return pe
             