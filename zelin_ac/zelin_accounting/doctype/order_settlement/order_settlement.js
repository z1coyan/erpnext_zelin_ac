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
	get_items(frm) {
		frappe.call({
			method: "get_items",
			doc: frm.doc,
			callback: function(r) {
				refresh_field("items");
			}
		});
	},
});
