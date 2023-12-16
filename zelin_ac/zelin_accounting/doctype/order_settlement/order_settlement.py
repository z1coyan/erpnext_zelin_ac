# Copyright (c) 2023, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt, getdate, datetime, get_first_day, get_last_day, formatdate


class OrderSettlement(Document):
    @frappe.whitelist()
    def get_items(self):
        from_date = get_first_day(datetime.date(
            year=cint(self.fiscal_year), month=cint(self.month), day=1))
        to_date = get_last_day(datetime.date(
            year=cint(self.fiscal_year), month=cint(self.month), day=1))               
        se = frappe.qb.DocType('Stock Entry')
        sed = frappe.qb.DocType('Stock Entry Detail')
        data = frappe.qb.from_(se
            ).join(sed
            ).on(se.name == sed.parent
            ).where(
                (se.company == self.company) &
                (se.docstatus == 1) &
                (se.posting_date >= from_date) &
                (se.posting_date <= to_date) &
                (se.purpose == 'Manufacture') &
				(sed.is_finished_item == 1 )
            ).select(
                se.name.as_('stock_entry'),
                se.posting_date,                
                sed.item_code,
                sed.t_warehouse.as_('warehouse'),
                sed.qty
            ).run(as_dict = True)
        self.items = []    
        for d in data:
            self.append('items', d)
