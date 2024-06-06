frappe.ui.form.on('Stock Entry', {
    setup: function (frm) {
		frm.set_query('expense_account', function (doc) {			
			return {
				filters: {
					'company': doc.company,
					'account_type': "Expense Account",
					"is_group": 0
				}
			}
		});
	},
    refresh: function (frm) {
		frm.set_query('reason_code', function (doc) {
			let filters = {};
			if (frm.doc.purpose === "Material Issue"){
				filters['for_material_issue'] = 1					
			} else {
				filters['for_material_receipt'] = 1
			}			
			return {
				filters: filters
			}
		});
	},
    reason_code(frm){
        if (frm.doc.reason_code){
            let filters = {'parent': frm.doc.reason_code,
                'company': frm.doc.company    
            }            
            frappe.call({
                method: "frappe.client.get_value",
    			args: {
    				doctype: "Material Movement Default Account",
    				filters: filters,
    				fieldname:"expense_account",
    				parent:"Material Move Reason Code"
    			},
            })
            .then(r=>{
                if (!r.exc){
                    frm.set_value('expense_account', r.message.expense_account);
                }
            })
        }
        else {
            frm.set_value('expense_account', "")
        }  
    }
})

// frappe.call({
// 	method: "frappe.client.get_list",
// 	args: {
// 		doctype: "Item Customer Detail",
// 		filters: {'customer_name':frm.doc.customer,
// 				  'ref_code': row.customer_item_code
// 				 },
// 		fields: ["parent as item_code"],
// 		parent:'Item',
// 		parent_doctype:'Item'
// 	},
// })
// .then((r) => {
// 	if (r.message) {
// 		frappe.model.set_value(cdt, cdn, 'item_code', r.message[0].item_code);
// 	}
// });
// }