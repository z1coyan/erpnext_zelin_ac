import frappe
import json
from zelin_ac.api import get_cached_value
from erpnext.stock.stock_ledger import (
    update_args_in_repost_item_valuation as original_update_args_in_repost_item_valuation )
from erpnext.stock import stock_ledger


def custom_update_args_in_repost_item_valuation(doc, index, args, distinct_item_warehouses, affected_transactions):
    original_update_args_in_repost_item_valuation(doc, index, args, distinct_item_warehouses, affected_transactions)
    if get_cached_value('enable_debug_repost_item_valuation'):
        doc.db_set(
			{
				"custom_items_to_be_repost": json.dumps(args, default=str),
				"custom_distinct_item_and_warehouse": json.dumps(
					{str(k): v for k, v in distinct_item_warehouses.items()}, default=str
				),
				"custom_affected_transactions": frappe.as_json(affected_transactions),
			}
		)

    if not frappe.flags.in_test:
        frappe.db.commit()

stock_ledger.update_args_in_repost_item_valuation = custom_update_args_in_repost_item_valuation