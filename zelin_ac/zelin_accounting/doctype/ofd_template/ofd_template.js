// Copyright (c) 2024, Vnimy and contributors
// For license information, please see license.txt

frappe.ui.form.on("OFD Template", {
	refresh(frm) {
        //抄自form.js set_df_property
        const  table_field = 'account';
        const grid = frm.fields_dict['accounts'].grid;
        const filtered_fields = frappe.utils.filter_dict(grid.docfields, {fieldname: table_field});
        if (filtered_fields.length) {
            $.each(frm.doc.accounts, function (i, d) {
                df = frappe.meta.get_docfield(
                    filtered_fields[0].parent,
                    table_field,
                    d.name
                );
                df.ignore_link_validation = 1;
            });
        }
	},
});

frappe.ui.form.on('OFD Template Item', {
    accounts_add(frm, dt, dn){
        df = frappe.meta.get_docfield(dt, 'account', dn);
        df.ignore_link_validation = 1;
    }
})
