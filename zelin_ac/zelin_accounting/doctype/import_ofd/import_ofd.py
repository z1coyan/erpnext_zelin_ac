# Copyright (c) 2024, Vnimy and contributors
# For license information, please see license.txt

import frappe
import re
from frappe.utils import flt
from frappe.model.document import Document
from zelin_ac.utils import get_ofd_xml, extract_amount


class ImportOFD(Document):
	def validate(self):
		self.parse_ofd()
		self.match_template()
		self.make_journal_entry()

	def parse_ofd(self):
		if not self.attach:
			self.attach = frappe.db.get_value('File',
				{
					'attached_to_doctype': self.doctype,
            		'attached_to_name': self.name
				},
				'file_url'
			)

		if self.attach and self.attach[-4:] == '.ofd':						
			content = get_ofd_xml(self.attach)
			self.contents = []
			for (k,v) in content.items():
				#返回的值是列表，取第1个值
				self.append('contents', {'field_name': k, 'field_value': v[0] or ''})
		if not self.attach and self.journal_entry:
			self.journal_entry = ''			

	def match_template(self):
		"""根据匹配条件表达式，匹配第一个满足条件的模板"""

		if self.contents:
			templates = frappe.get_all('OFD Template', fields=['name', 'match_condition'], as_list=1)
			for (template_name, match_condition) in templates:
				try:
					if frappe.safe_eval(match_condition, None, {r.field_name:r.field_value for r in self.contents}):
						self.ofd_template = template_name
						break
				except:
					traceback = frappe.get_traceback(with_context=True)
					frappe.log_error("Import OFD match template failure", traceback)

	def get_created_journal_entry(self, template_doc, ofd_doc):
		"""要考虑参考号跨银行唯一问题"""

		cheque_no = template_doc.cheque_no
		if cheque_no and '{{' in cheque_no:
			cheque_no = frappe.render_template(cheque_no, ofd_doc)
		return frappe.db.get_value('Journal Entry', {'cheque_no': cheque_no, 'docstatus': ('<', 2)})

	def make_journal_entry(self):
		"""
		处理多币种，多明细行，多个文件上传
		"""

		if not self.journal_entry and self.ofd_template:
			#要检查重复 用reference number, 即cheque_no字段
			template_doc = frappe.get_doc('OFD Template', self.ofd_template)
			ofd_doc = {r.field_name:r.field_value for r in self.contents}
			ofd_doc['doc'] = frappe._dict(ofd_doc)	#也支持通过doc.field方式获取字段值
			journal_entry_name = self.get_created_journal_entry(template_doc, ofd_doc)
			if journal_entry_name:
				self.message = f'日记账凭证 {journal_entry_name} 已经创建过了'
			else:
				je_doc = frappe.new_doc("Journal Entry")
				meta = template_doc.meta
				fields = [f.fieldname for f in template_doc.meta.fields 
					if f.fieldtype in ['Data','Check', 'Link'] and f.fieldname not in ('template_code','template_name')]
				for field in fields:
					value = template_doc.get(field)
					if value and isinstance(value, str) and '{{' in value:
						value = frappe.render_template(value, ofd_doc)
					if value:
						je_doc.set(field, value)
					#print(f"field={field}, value={value}")
				meta = template_doc.accounts[0].meta
				child_fields = [f.fieldname for f in meta.fields]
				for row in template_doc.accounts:
					je_row_dict = frappe._dict()
					for field in child_fields:
						value = row.get(field)
						if value and isinstance(value, str) and '{{' in value:
							value = frappe.render_template(value, ofd_doc)
						#清除金额字段货币前缀	
						if (('debit' in field or 'credit' in field) or field =='exchange_rate') and value:
							value = flt(extract_amount(value))
						if value:	
							je_row_dict[field] = value
						#print(f"field={field}, value={value}")
					if je_row_dict.account:
						je_doc.append('accounts', je_row_dict)
					auto_round_off_account(je_doc)
				je_doc.insert(ignore_permissions=1)
				self.journal_entry = je_doc.name
				frappe.get_doc({
					'doctype': 'File',
					'file_url': self.attach,
					'attached_to_doctype': je_doc.doctype,
					'attached_to_name': je_doc.name
				}).insert(ignore_permissions=1)
				self.message = f'日记账凭证 {self.journal_entry} 创建成功'

def auto_round_off_account(doc):
	"""
	处理因汇率转换产生的圆整差异，自动添加圆整差异行
	"""

	if doc.company and doc.multi_currency:
		doc.set_amounts_in_company_currency()
		doc.set_total_debit_credit()
		if doc.difference and abs(doc.difference) < 0.5:
			round_off_account = frappe.db.get_value('Company', doc.company, 'round_off_account')
			if round_off_account:
				debit_or_credit = 'credit' if doc.difference >0 else 'debit'
				doc.append('accounts',{
					'account':round_off_account,
					f'{debit_or_credit}_in_account_currency': abs(doc.difference),
					debit_or_credit: abs(doc.difference)
				})	