// Copyright (c) 2024, Vnimy and contributors
// For license information, please see license.txt

frappe.ui.form.on("Month End Tracking", {
    onload: function(frm){
        if (frm.is_new()){
            frm.set_value('year', erpnext.utils.get_fiscal_year(frappe.datetime.get_today()));
            frm.set_value('month', new Date().getMonth() + 1);
        }
    },
	refresh: function(frm) {
        frappe.db.count("Month End Tracking", frm.doc.erpnext_company).then((count) => {
			if (count===0) {
                frm.add_custom_button('导入范例数据', function() {
                    frm.events.import_example_data(frm);
                });
			}
		});		
	},

	import_example_data(frm) {
		frm.call('get_example_data').then(r => {
			frm.set_value(r.message);
		});
	}
})