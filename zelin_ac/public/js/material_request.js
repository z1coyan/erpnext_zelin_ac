frappe.ui.form.on('Material Request', {
    setup: function (frm) {
		frm.set_query('reason_code', function (doc) {			
			return {
				filters: {
					for_material_issue: 1					
				}
			}
		});
	}
})