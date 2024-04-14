# Copyright (c) 2024, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ZelinAccountingSettings(Document):
	def on_update(self):
		before_save = self.get_doc_before_save()
		if (before_save and 
			before_save.disable_toggle_debit_credit_if_negative != self.disable_toggle_debit_credit_if_negative):
			frappe.cache().delete_value('disable_toggle_debit_credit_if_negative')
