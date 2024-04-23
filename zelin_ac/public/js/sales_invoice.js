frappe.ui.form.on('Sales Invoice', {
	refresh: function(frm) {
		
	}
})

const multi_select_dn_item = function(frm){
	let opts = {
		data_fields:[
		{
			"label": __(  "Delivery Note"),
			"fieldname": "delivery_note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"width": 160,
		},
		{
			"label": __(  "Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": __(  "Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": __(  "Billed Amount"),
			"fieldname": "billed_amount",
			"fieldtype": "Currency",
			"width": 100
		},
		{            
            "fieldname": "child_name",
            "fieldtype": "Data"
        }
	]}

	const d = new frappe.ui.form.MultiSelectDialog({
		doctype: "Delivery Note",
		target: frm,
		date_field: 'posting_date',
		setters: {
			customer: frm.doc.customer || undefined,
		},
		child_columns: ['delivery_note','item_code','billed_amount','child_name'],
		get_query: function () {
			var filters = {
				docstatus: 1,
				company: frm.doc.company,
				is_return: 0,
				from_date:'2024-03-14',
				to_date:'2024-04-14'
			};
			if (frm.doc.customer) filters["customer"] = frm.doc.customer;
			return {
				query: "zelin_ac.queries.get_delivery_notes_to_be_billed",
				filters: filters,
			};
		},
		add_filters_group: 1,
		size: "extra-large",
		action: function (selections, args) {
			let values = selections;
			if (values.length === 0) {
				frappe.msgprint(___(  "Please select {0}", [opts.source_doctype]));
				return;
			}
			opts.source_name = values;
			const data_values = d.get_values();
			d.dialog.hide();
			frappe.call({
				// Sometimes we hit the limit for URL length of a GET request
				// as we send the full target_doc. Hence this is a POST request.
				type: "POST",
				method: "frappe.model.mapper.map_docs",
				args: {
					method: opts.method,
					source_names: opts.source_name,
					target_doc: cur_frm.doc,
					args: opts.args,
				},
				freeze: true,
				freeze_message: ___(  "Mapping {0} ...", [opts.source_doctype]),
				callback: function (r) {
					if (!r.exc) {
						frappe.model.sync(r.message);
						cur_frm.dirty();
						cur_frm.refresh();
					}
				},
			});
		},
	});
}