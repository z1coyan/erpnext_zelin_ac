# Copyright (c) 2024, Vnimy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PrintLog(Document):
	pass


def is_system_manager(user):
	return bool(frappe.db.exists('Has Role', {
			'role': 'System Manager',
			'parenttype':'User',
			'parent': user
		}))

def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user
	if not is_system_manager(user):
		return f"""(`tabPrint Log`.`owner`={frappe.db.escape(user)})"""

def has_permission(doc, user):
	if is_system_manager(user) or doc.owner == user:
		return True

	return False