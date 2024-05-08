// Copyright (c) 2024, Vnimy and contributors
// For license information, please see license.txt

frappe.query_reports["GR IR Reconciliation"] = {
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
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				if (!frappe.query_report.filters) return;
				return frappe.db.get_link_options("Supplier", txt);
			},			
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			hidden: 1,
			options: "Line Item\nDoc\nSupplier",
		},
		{
			fieldname: "hide_fully_matched",
			label: __("Hide Fully Matched"),
			fieldtype: "Check",
			default: 1
		},
    ],
};
