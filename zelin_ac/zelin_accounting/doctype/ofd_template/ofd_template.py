# Copyright (c) 2024, Vnimy and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class OFDTemplate(Document):
	def save(self, *args, **kwargs):
		self.flags.ignore_links = True
		return super().save(*args, **kwargs)

	def insert(self, *args, **kwargs):
		self.flags.ignore_links = True
		return super().insert(*args, **kwargs)