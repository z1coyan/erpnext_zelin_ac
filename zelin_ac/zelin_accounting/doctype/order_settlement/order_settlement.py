# Copyright (c) 2023, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.meta import get_field_precision
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
                (sed.is_scrap_item == 0) &
                (sed.is_finished_item == 1)
            ).select(
                se.name.as_('stock_entry'),
                se.work_order,
                se.posting_date,
                se.posting_time,                
                sed.item_code,
                sed.t_warehouse.as_('warehouse'),
                sed.additional_cost.as_('included_expense'),
                sed.qty,
                sed.amount
            ).orderby(se.posting_date
            ).orderby(se.posting_time
            ).run(as_dict = True)
        #通过工单获取工站
        wo_workstation_map = frappe._dict(frappe.get_all('Job Card', 
            filters = {
                'docstatus' : 1,
                'work_order': ('in', {row.work_order for row in data})
            },
            fields = ['work_order','workstation'],
            as_list = 1))    
        self.items = []    
        for d in data:
            d.workstation = wo_workstation_map.get(d.work_order)            
            self.append('items', d)
        self.set_expenses()

    def validate(self):
        if not self.get("items"):
            self.get_items()
        self.check_mandatory()        
        self.set_applicable_expenses_on_item()

    def check_mandatory(self):
        if not self.get("items"):
            frappe.throw(_("Please enter Order Settlement Items"))

    def set_expenses(self):
        included_expense_map = {}
        for row in self.items:
            workstation = row.workstation or ''
            included_expense_map.setdefault(workstation, 0)
            included_expense_map[workstation] += row.included_expense
        
        existing_workstations = set()
        if self.expenses:
            existing_workstations = {row.workstation for row in self.expenses}
            for row in self.expenses:
                workstation = row.workstation or ''
                row.included_expense = included_expense_map.get(workstation, 0)
                row.allocatable_expense = row.actual_expense - row.included_expense
                row.variance = row.allocatable_expense - (row.allocated_expense or 0)

        for (workstaion, included_expense) in included_expense_map.items():
            if workstaion not in existing_workstations:
                self.append('expenses', {
                    'workstation': workstaion,
                    'included_expense' : included_expense
                })

    def set_applicable_expenses_on_item(self):
        """
        {'ws1':
            {allocatable: allocatable(actual - total included expense),
             base:total included expense,
             allocation_rate: allocatable/base,
             allocated_expense:
             variance: allocatable - allocated
             }
        }}
        """

        if not self.expenses: return

        precision = get_field_precision(frappe.get_meta("Order Settlement Item").get_field("allocated_expense"))
        allocation_map = {}
        allocatable_expense_map = {}
        for row in self.items:
            workstation = row.workstation or ''
            allocation_map.setdefault(workstation, frappe._dict({'base':0, 'allocated_expense':0}))
            allocation_map[workstation].base += row.included_expense

        for row in self.expenses:
            workstation = row.workstation or ''
            workstation_data = allocation_map.get(workstation, frappe._dict({'base':0, 'allocated_expense':0}))
            if row.actual_expense and row.included_expense:
                row.allocatable_expense = row.actual_expense - row.included_expense
                workstation_data['allocatable'] = row.allocatable_expense
                workstation_data['variance'] = row.allocatable_expense
                if workstation_data.get('base'):
                    workstation_data['allocation_rate'] = workstation_data['allocatable'] / workstation_data['base']
        
        for row in self.items:
            workstation = row.workstation or ''
            workstation_data = allocation_map.get(workstation, frappe._dict({'base':0, 'allocated_expense':0}))
            if row.included_expense and workstation_data and workstation_data.allocation_rate:
                row.allocated_expense = flt(row.included_expense * workstation_data.allocation_rate, precision)
                workstation_data.allocated_expense += row.allocated_expense
                variance = workstation_data.variance - row.allocated_expense
                #将最后的尾差分到最后一项上
                if -0.1 <= variance <= 0.1:
                    row.allocated_expense += variance
                    workstation_data.allocated_expense += variance
                    variance = 0
                workstation_data.variance = variance

        # 更新费用分摊情况        
        for row in self.expenses:
            workstation = row.workstation or ''
            workstation_data = allocation_map.get(workstation, frappe._dict({}))
            row.update({
                'allocated_expense': workstation_data.allocated_expense,
                'variance': workstation_data.variance
            })

    def validate_applicable_expenses_for_item(self):
        pass

    def on_submit(self):
        self.validate_applicable_expenses_for_item()
        self.update_cost()

    def on_cancel(self):
        self.update_cost()

    def update_cost(self):
        """
            将本月工站实际费用-已结转库存费用的差异金额基于已结转库存费用
            分摊到已入库成品，并调用更新入库时间点后续物料移动凭证(成本追溯调整)
        """

        company_doc = frappe.get_cached_doc('Company', self.company)
        expenses_included_in_valuation = company_doc.expenses_included_in_valuation
        if not expenses_included_in_valuation:
            frappe.throw(_("Expenses Included in Valuation in comany master missing"))
        
        for d in self.get("items"):
            allocated_expense = d.allocated_expense if self.docstatus == 1 else -1 * d.allocated_expense
            if not allocated_expense: continue
            doc = frappe.get_doc('Stock Entry', d.stock_entry)
            #取消原物料及会计凭证
            doc.docstatus = 2
            sl_entries = []
            finished_item_row = doc.get_finished_item_row()
            doc.get_sle_for_source_warehouse(sl_entries, finished_item_row)
            doc.get_sle_for_target_warehouse(sl_entries, finished_item_row)
            sl_entries.reverse()
            #允许负库存参数用于处理库存已被完全耗用，追溯调整结算时反冲出现负库存
            doc.make_sl_entries(sl_entries, allow_negative_stock=True)
            #doc.update_stock_ledger()
            doc.make_gl_entries_on_cancel()
            #添加结算费用明细行及金额
            description = "{0}Expense variance settlement".format("" if self.docstatus == 1 else "Cancel ")
            doc.append('additional_costs',{
                'expense_account': expenses_included_in_valuation,
                'exchange_rate': 1,
                'account_currency': company_doc.default_currency or 'CNY',
                'base_amount': allocated_expense,
                'amount': allocated_expense,
                'description': _(description)
            })
            doc.total_additional_costs -= allocated_expense
            #重新计算成品入库成本价
            doc.calculate_rate_and_amount()
            doc.docstatus = 1
            doc.update_stock_ledger()
            doc.make_gl_entries()
            doc.repost_future_sle_and_gle()
            #直接使用save会触发不必要的校验，产生提交后某字段不能更新错误
            doc.db_update()
            doc.update_children()