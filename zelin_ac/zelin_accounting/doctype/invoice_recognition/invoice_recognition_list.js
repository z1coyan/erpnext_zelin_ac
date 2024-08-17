frappe.listview_settings["Invoice Recognition"] = {
    add_fields: ["status"],
    has_indicator_for_draft: 1,
    get_indicator: function (doc) {
        if (doc.status == "Draft") {
            return [__("Draft"), "orange", "status,=,Draft"]
        } else if (doc.status == "Recognized") {
            return [__("Recognized"), "green", "status,=,Recognized"]
        } else if (doc.status == "Cancelled") {
            return [__("Cancelled"), "red", "status,=,Cancelled"]
        } else if (doc.status == "Used") {
            return [__("Used"), "blue", "status,=,Used"]
        }
    }
}