// Copyright (c) 2023, Vnimy and contributors
// For license information, please see license.txt

frappe.ui.form.on('Order Settlement', {
	onload: function(frm) {        
		if (frm.is_new()){
			const fiscal_year = erpnext.utils.get_fiscal_year(frappe.datetime.get_today());
			fiscal_year && frm.set_value('fiscal_year', fiscal_year);
			const date = new Date();
			const month = date.getMonth() + 1;
			frm.set_value('month', month);
		}
	},
	refresh(frm){
		if (frm.doc.docstatus !== 0){
			frm.add_custom_button(__('Repost Item Valuation'), () => {
				const vouchers = frm.doc.items.map(
					r=>{return r.stock_entry}
				)
				frappe.set_route('List', 'Repost Item Valuation', 
					{
						company: frm.doc.company,
						//creation: ['>', frm.doc.modified],
						//生成的成本调整凭证记账日期是入库单的记账日期，
						//posting_date: frm.doc.modified.split(' ')[0],
						voucher_type:'Stock Entry',					
						voucher_no: ['in', vouchers]});
			}, __('View'));
		}
	},	
	get_items(frm) {
		frappe.call({
			method: "get_items",
			doc: frm.doc,
			callback: function(r) {
				refresh_field("items");
				refresh_field("expenses");
				frm.dirty();
			}
		});
	},
});
