frappe.query_reports["Delivery Notes To Bill"] = {
	filters: [
        {
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "exclude_in_draft_invoice",
			label: __("Exclude in Draft Invoice"),
			fieldtype: "Check",
			default: 1
		},
    ],
    get_datatable_options(options) {
		 // loops on each column and make one ore more of them editable
		 options.columns.forEach(function(column, i) {
			// column id i want to make editable
			if(column.id == "my_qty") {
				column.editable = true
			}
		});
/*
上面的修改被系统覆盖掉了，下面的可以
datatable.options.columns[5].editable=true
datatable.refresh()
如何获取变更后的值在rowmanager的rows content字段里，没有更新data变量
*/
		return Object.assign(options, {
			treeView: true,
			checkedRowStatus: false,
			checkboxColumn: true,
			events: {
				onCheckRow: row => {
					update_selection(row)
				},
/*
 				onSubmitEditing: function (cell) {
					// rowValues : all cell values from row before edition
					// cellId : key id of cell edited
					// newVal : edited val
					let [rowValues, cellId, newVal] = cell;
					if(cellId == "your_editable_id") {
						frappe.call({
							method: "your.method",
							type: "GET",
							args: {name: rowValues.id, qty: newVal}, // for example
							callback: function (r) {
								if (r.message) {
									frappe.msgprint(__(r.message));
								}
							},
						});
					}
				}, 
*/
			},
		})
	},
	onload: reportview => {
		manage_buttons(reportview)
	},
	refresh: reportview => {
		manage_buttons(reportview)
	},
}

function manage_buttons(reportview) {
	reportview.page.add_inner_button(
		__('Create One Sales Invoice'),
		function () {
			create_sales_invoice()
		},
		//'Create'
	)

	// these don't seem to be working
	$(".btn-default:contains('Create Card')").addClass('hidden')
	$(".btn-default:contains('Set Chart')").addClass('hidden')
}

function create_sales_invoice() {
	let values = frappe.query_report.get_filter_values()
	let selected_rows = frappe.query_report.datatable.rowmanager.getCheckedRows()
	let source_names = frappe.query_report.datatable.datamanager.data.filter((row, index) => {
		return selected_rows.includes(String(index)) ? row : false
	})
	if (!source_names.length) {
		frappe.show_alert({ message: 'Please select one or more rows.', seconds: 5, indicator: 'red' })
	} else {
        frappe.call({
            method: "zelin_ac.api.create_sales_invoice",
            args: {
                source_names: source_names
            },
            callback: function(r) {
                if (r.message) {
                    var doclist = frappe.model.sync(r.message);
                    frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                }
            }
        })
	}
}

function update_selection(row) {
	if (row !== undefined && !row[5].content) {
		const toggle = frappe.query_report.datatable.rowmanager.checkMap[row[0].rowIndex]
	}
}