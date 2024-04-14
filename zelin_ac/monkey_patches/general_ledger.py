import frappe
from erpnext.accounts.general_ledger import (
    distribute_gl_based_on_cost_center_allocation,
	toggle_debit_credit_if_negative,
	merge_similar_entries)
from erpnext.accounts import general_ledger

def custom_process_gl_map(gl_map, merge_entries=True, precision=None):
    """
		标准功能会基于借货净值决定借货方向，在模块设置可禁用此标准功能
		此功能支持借货方负数(红字冲销)
    """

    def get_disable_toggle_debit_credit_if_negative():
        return frappe.db.get_single_value('Zelin Accounting Settings',
            'disable_toggle_debit_credit_if_negative')

    if not gl_map:
        return []

    if gl_map[0].voucher_type != "Period Closing Voucher":
        gl_map = distribute_gl_based_on_cost_center_allocation(gl_map, precision)

    if merge_entries:
        gl_map = merge_similar_entries(gl_map, precision)
    
    disable_toggle_debit_credit_if_negative = frappe.cache().get_value(
        'disable_toggle_debit_credit_if_negative', get_disable_toggle_debit_credit_if_negative
    )
    if not disable_toggle_debit_credit_if_negative:
        gl_map = toggle_debit_credit_if_negative(gl_map)

    return gl_map

general_ledger.process_gl_map = custom_process_gl_map