import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.stock.doctype.delivery_note.delivery_note import update_billed_amount_based_on_so
from erpnext.accounts.general_ledger import get_round_off_account_and_cost_center
from frappe.query_builder.functions import Sum


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

class CustomSalesInvoice(SalesInvoice):
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

        def get_enable_dni_billed_qty():
            return frappe.db.get_single_value('Zelin Accounting Settings',
                'enable_dni_billed_qty')

        enable_dni_billed_qty = frappe.cache().get_value('enable_dni_billed_qty', get_enable_dni_billed_qty)
        if not enable_dni_billed_qty:
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
                elif d.so_detail :
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
             