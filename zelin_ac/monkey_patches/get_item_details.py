import frappe
from erpnext.stock import get_item_details
from erpnext.stock.get_item_details import (
	get_price_list_rate_for as original_get_price_list_rate_for,
	get_item_price as original_get_item_price,
	check_packing_list
)
from frappe.query_builder import Case
from frappe.query_builder.functions import IfNull, Sum


def get_enable_scale_price():
	return frappe.db.get_single_value('Zelin Accounting Settings', 'enable_scale_price')

def custom_get_price_list_rate_for(args, item_code):
	"""
	增加对qty参数的处理，由物料明细行中输入数量触发调用时传入
	原来调用get_item_price 替换为了custom_get_item_price
	"""

	enable_scale_price = frappe.cache().get_value('enable_scale_price', get_enable_scale_price)
	if not enable_scale_price:
		return original_get_price_list_rate_for(args, item_code)
	else:
		item_price_args = {
			"item_code": item_code,
			"price_list": args.get("price_list"),
			"customer": args.get("customer"),
			"supplier": args.get("supplier"),
			"uom": args.get("uom"),
			"transaction_date": args.get("transaction_date"),
			"batch_no": args.get("batch_no"),
			"qty": args.get("qty"),   #增加qty参数
		}

		item_price_data = 0
		price_list_rate = custom_get_item_price(item_price_args, item_code)
		if price_list_rate:
			desired_qty = args.get("qty")
			if desired_qty and check_packing_list(price_list_rate[0][0], desired_qty, item_code):
				item_price_data = price_list_rate
		else:
			for field in ["customer", "supplier"]:
				del item_price_args[field]

			general_price_list_rate = custom_get_item_price(
				item_price_args, item_code, ignore_party=args.get("ignore_party")
			)

			if not general_price_list_rate and args.get("uom") != args.get("stock_uom"):
				item_price_args["uom"] = args.get("stock_uom")
				general_price_list_rate = custom_get_item_price(
					item_price_args, item_code, ignore_party=args.get("ignore_party")
				)

			if general_price_list_rate:
				item_price_data = general_price_list_rate

		if item_price_data:
			if item_price_data[0][2] == args.get("uom"):
				return item_price_data[0][1]
			elif not args.get("price_list_uom_dependant"):
				return flt(item_price_data[0][1] * flt(args.get("conversion_factor", 1)))
			else:
				return item_price_data[0][1]

get_item_details.get_price_list_rate_for = custom_get_price_list_rate_for

def custom_get_item_price(args, item_code, ignore_party=False):
	"""
	基于传入参数中是否有qty,如有阶梯价则替换物料价格主表中的标准价
	"""

	data = original_get_item_price(args, item_code, ignore_party=False)
	qty = args.get('qty')
	enable_scale_price = frappe.cache().get_value('enable_scale_price', get_enable_scale_price)
	if data and enable_scale_price and qty:
		ipsp = frappe.qb.DocType('Item Price Scale Price')
		item_price_names = [d[0] for d in data]
		scale_price_map = frappe._dict(frappe.qb.from_(ipsp
		).select(ipsp.parent, ipsp.price_list_rate
		).where(
			ipsp.parent.isin(item_price_names) &			
			(ipsp.scale_qty<=qty) &
			(ipsp.upper_limit_qty>qty)					
		).run())
		if scale_price_map:
			#替换为阶梯价
			data = [(d[0],scale_price_map.get(d[0]) or d[1], d[2]) for d in data]		
				
	return data

get_item_details.get_item_price = custom_get_item_price