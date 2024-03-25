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
			return {
				filters: {
					for_material_issue: frm.doc.purpose === "Material Issue",
					for_material_receipt: frm.doc.purpose === "Material Receipt"					
				}
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