# Copyright (c) 2024, xu and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
import re
from frappe.model.document import Document
from zelin_ac.baidu_api import get_invoice_info
from frappe.desk.reportview import get_match_cond
from frappe.utils import today


class InvoiceRecognition(Document):
	def save(self, *args, **kwargs):
		"""处理从发票识别出来的公司不是系统内存在的公司"""

		self.flags.ignore_links = True
		return super().save(*args, **kwargs)

	def insert(self, *args, **kwargs):
		self.flags.ignore_links = True
		return super().insert(*args, **kwargs)

	def validate(self):
		self.get_invoice_info()
		self.set_missing_values()
		self.set_status()
		self.validate_invoice_number(throw=False)

	def set_status(self, status=None):
		if self.docstatus == 0:
			if status:
				self.status = status
			elif not self.attach:
				self.status = "Draft"
			elif self.data:
				self.status = "Recognized"
		elif self.docstatus == 1:
			if self.reference_doctype and self.reference_name:
				if not status:
					# 被关联的时候状态变更为已使用
					self.status = "Used"
				else:
					# 报销单支付的时候状态变更为已支付
					self.status = status
		elif self.docstatus == 2:
			self.status = "Cancelled"
		
	def on_submit(self):
		if not self.attach:
			frappe.throw("请上传发票")
		if not self.grand_total or self.grand_total == "0":
			frappe.throw("发票总额未被识别，请联系管理员优化识别")
		self.validate_invoice_number()

	def set_missing_values(self):
		if not self.company:
			self.company = frappe.get_value('Employee', self.employee, 'company')

	def is_same_file_recognized(self):
		"""根据content_hash判断"""
		
		invoice_recognition_dt = frappe.qb.DocType('Invoice Recognition')
		file_dt = frappe.qb.DocType('File')
		content_hash = frappe.db.get_value('File', {'file_url': self.attach},'content_hash')
		recognized_invoice = (
			frappe.qb.from_(invoice_recognition_dt
			).join(file_dt
			).on(invoice_recognition_dt.attach==file_dt.file_url
			).where(
				(file_dt.content_hash == content_hash) &
				(invoice_recognition_dt.name != self.name) &
				(invoice_recognition_dt.status.notin(['Draft','Cancelled']))
			).distinct(
			).select(invoice_recognition_dt.name
			).run(pluck=1)   
		)		
		if recognized_invoice:
			self.set_status('Recognize Failed')
			self.error_message = f"其它发票识别记录{','.join(recognized_invoice)}已经识别过相同文件了"[:140]
			return True

	def get_invoice_info(self, re_recognize=False):
		if not self.attach:
			frappe.msgprint("请上传发票",alert=True)
			return
		
		if self.data and not re_recognize:
			return
		suffix = self.attach[-4:].lower()
		if suffix not in ['.pdf','.jpg','.png']:
			frappe.throw("只支持识别.pdf,.jpg,.png后缀的文件")

			return
		if re_recognize or not self.is_same_file_recognized():
			return self.recognize_invoice()	

	def recognize_invoice(self):

		def get_field_value(field_name, index=0, default=None):  
			"""从给定数据中获取指定字段名和索引的值，如果索引错误则返回默认值。"""  
			try:  
				field_data = info.get(field_name, [])  
				return field_data[index].get('word', default) if field_data else default  
			except IndexError:  
				return default
		
		data = get_invoice_info(self.attach)
		#if frappe.get_conf().developer_mode ==1:
		#	frappe.log_error(title='发票验证结果',message=data)
		if not data:
			return

		self.data = data
		if isinstance(data, str):
			data_dict = frappe.parse_json(data)
		info = frappe.parse_json(data_dict.words_result[0].get('result'))

		header_field_mapping = {  
			'company': 'PurchaserName',  
			'party': 'SellerName',  
			'invoice_type_org': ['InvoiceType', 'InvoiceTypeOrg'],  
			'invoice_num': 'InvoiceNum',  
			'invoice_date': ['InvoiceDate','Date'],  
			'invoice_code': 'InvoiceCode',  
			'grand_total': 'AmountInFiguers',  
			'total_tax': 'TotalTax'  
		}  

		if info.PurchaserRegisterNum or info.PurchaserName:
			company_tax_id = info.PurchaserRegisterNum[0].get('word')
			if company_tax_id:
				self.company = frappe.db.get_value('Company', {'tax_id':company_tax_id})
			if not self.company:
				self.company = info.PurchaserName[0].get('word')
			self.party = info.SellerName[0].get('word')

			if info.InvoiceType:
				# 纸质加油发票可能的结果
				self.invoice_type_org = info.InvoiceType[0].get('word')
			elif info.InvoiceTypeOrg:
				self.invoice_type_org = info.InvoiceTypeOrg[0].get('word')

			self.invoice_num = info.InvoiceNum[0].get('word')
			if info.InvoiceDate:
				self.invoice_date = info.InvoiceDate[0].get('word')
			elif self.Date:
				self.invoice_date = info.Date[0].get('word')

			# 发票代码可能不存在
			if info.InvoiceCode:
				self.invoice_code = info.InvoiceCode[0].get('word')

			self.grand_total = info.AmountInFiguers[0].get('word')
			self.total_tax = info.TotalTax[0].get('word')
		
		row_field_mapping = {  
			'item_name': 'CommodityName',    
			'model_type': 'CommodityType',  
			'uom': 'CommodityUnit',  
			'qty': 'CommodityNum',  
			'rate': 'CommodityPrice',  
			'amount': 'CommodityAmount',  
			'tax_rate': 'CommodityTaxRate',  
			'tax_amount': 'CommodityTax'  
		}
		self.items = []		
		if info.CommodityName:
			row_cnt = len(info.CommodityName)
			for idx in range(0, row_cnt):
				row = {k:get_field_value(v, idx) for (k,v) in row_field_mapping.items()}
				# 内容长这样 *信息技术服务*软件使用技术咨询与支持"
				item_name = row.get('item_name',"")
				item_name_list = item_name.split("*")
				if len(item_name_list) > 1:
					row['item_name'] = item_name_list[1]
				if len(item_name_list) > 2:
					row['item_type'] = item_name_list[2]
				self.append("items", row)

		elif info.TotalFare:
			# 出租车发票
			self.grand_total = info.TotalFare[0].get('word')
			if info.InvoiceCode:
				self.invoice_code = info.InvoiceCode[0].get('word')
			self.invoice_num = info.InvoiceNum[0].get('word')
			if info.InvoiceDate:
				self.invoice_date = info.InvoiceDate[0].get('word')
			elif info.Date:
				self.invoice_date = info.Date[0].get('word')

			if not info.PurchaserName:
				self.company = frappe.get_value('Employee', self.employee, 'company')
		elif info.ticket_rates:
			# 火车票
			self.grand_total =  re.search(r'\d+(\.\d+)?', info.ticket_rates[0].get('word')).group()
			if info.date:
				self.invoice_date = info.date[0].get('word')
			if info.serial_number:
				self.invoice_num = info.serial_number[0].get('word')
			if not info.PurchaserName:
				self.company = frappe.get_value('Employee', self.employee, 'company')

		if not self.grand_total or self.grand_total == 0:
			# 仍未提取出来信息，检查是否为定额发票
			if info.invoice_rate_in_figure:
				self.grand_total = info.invoice_rate_in_figure[0].get('word')
			if info.invoice_type:
				self.invoice_type_org = info.invoice_type[0].get('word')
			if info.invoice_code:
				self.invoice_num = info.invoice_code[0].get('word')

		# 如果同时有发票代码和发票号码，则同时提取
		if info.invoice_code and info.invoice_number:
			self.invoice_code = info.invoice_code[0].get('word')
			self.invoice_num = info.invoice_number[0].get('word')

		self.set_status()

	def validate_invoice_number(self, throw=True):
		error_message = None

		if self.company and not frappe.db.exists('Company', self.company):
			self.error_message = "非本系统现有公司发票"
		else:			
			if self.invoice_code:
				# 有发票代码的时候
				ir_list = frappe.get_all('Invoice Recognition', 
					filters={
						'invoice_code': self.invoice_code, 
						'invoice_num': self.invoice_num,
						'name':['!=', self.name],
						'docstatus':['<', 2]
					}
				)
				if len(ir_list) > 0:
					error_message = "发票代码和发票号码和单据{0}重复".format(ir_list[0].name)
			else:
				ir_list = frappe.get_all('Invoice Recognition', 
					filters={
						'invoice_num': self.invoice_num,
						'name':['!=', self.name],
						'docstatus':['<', 2]
					}
				)
				if len(ir_list) > 0:
					error_message = "发票号码和单据{0}重复".format(ir_list[0].name)
							
			if not self.grand_total:
				error_message = "未解析出金额，无效发票"
			
		if error_message:
			self.set_status('Recognize Failed')
			self.error_message = error_message
			if throw:
				frappe.throw(error_message)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def invoice_recogniton_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	doctype = "Invoice Recognition"
	conditions = []
	if isinstance(filters, str):
		filters = json.loads(filters)

	filters_condition = ""
	if filters.get('company'):
		filters_condition += " and (`tabInvoice Recognition`.`company` = '{0}' or `tabInvoice Recognition`.`company` is null)".format(filters.get('company'))
	if filters.get('grand_total'):
		filters_condition += " and `tabInvoice Recognition`.grand_total between {0} and {1}".format(filters.get('grand_total'), filters.get('grand_total')*1.13)
	if filters.get('employee'):
		filters_condition += " and `tabInvoice Recognition`.`employee` = '{0}'".format(filters.get('employee'))
	if filters.get('expense_type'):
		filters_condition += " and (`tabInvoice Recognition`.`expense_type` = '{0}' or `tabInvoice Recognition`.`expense_type` is null)".format(filters.get('expense_type'))

	meta = frappe.get_meta(doctype, cached=True)
	searchfields = meta.get_search_fields()

	columns = ""
	extra_searchfields = [field for field in searchfields if field not in ["name", "description"]]
	if extra_searchfields:
		columns += ", " + ", ".join(extra_searchfields)

	searchfields = searchfields + [
		field
		for field in [searchfield or "name"]
		if field not in searchfields
	]
	searchfields = " or ".join([field + " like %(txt)s" for field in searchfields if field not in  ('grand_total','company')])
	
	result = frappe.db.sql(
		"""select
			name {columns}
		from `tabInvoice Recognition`
		where 
			docstatus = 1
			and status = "Recognized"
			and ({scond})
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, party), locate(%(_txt)s, party), 99999),
			idx desc,
			modified desc
		limit %(start)s, %(page_len)s """.format(
			columns=columns,
			scond=searchfields,
			fcond=filters_condition,
			mcond=get_match_cond(doctype).replace("%", "%%"),
		),
		{
			"txt": "%%%s%%" % txt,
			"_txt": txt.replace("%", ""),
			"start": start,
			"page_len": page_len,
		},
		as_dict=as_dict,
	)  

	return result


@frappe.whitelist()
def make_expense_claim(args):
	if isinstance(args, str):
		args = json.loads(args)
	
	if type(args) == dict:
		name = args.get('name')
		doc = frappe.get_doc('Invoice Recognition', name)
		if doc.status == 'Recognized':
			expense_claim = frappe.new_doc("Expense Claim")
			expense_claim.employee = doc.employee
			expense_claim.project = doc.project

			department = frappe.db.get_value('Employee', doc.employee, 'department')
			if department:
				expense_approver = frappe.db.get_value(
					"Department Approver",
					{"parent": department, "parentfield": "expense_approvers", "idx": 1},
					"approver",
				)
				expense_claim.expense_approver = expense_approver
			# 添加公司信息
			if doc.company:
				company = doc.company
				expense_claim.company = doc.company
			else:
				company = frappe.get_value('Employee', doc.employee, 'company')
				expense_claim.company = company

			if doc.expense_type:
				expense_claim.expense_type = doc.expense_type

			default_payable_account = frappe.get_cached_value(
				"Company", company, "default_expense_claim_payable_account"
			)
			expense_claim.payable_account = default_payable_account

			default_cost_center = frappe.get_cached_value("Company", company, "cost_center")
			expense_claim.cost_center = default_cost_center

			# 附加报销信息
			account = frappe.db.get_value(
				"Expense Claim Account", {"parent": doc.expense_type, "company": company}, "default_account"
			)
			expense_claim.append(
				"expenses",
				{
					"expense_date": today(),
					"expense_type": doc.expense_type,
					"amount": doc.grand_total,
					"invoice_recognition": doc.name,
					"cost_center": default_cost_center,
					"default_account":account,
				},
			)

			expense_claim.save(ignore_permissions=True)
			return expense_claim
	else:
		if len(args) == 1:
			return make_expense_claim(args[0])
		else:
			validate_ir_list(args)
			name = args
			expense_claim = frappe.new_doc("Expense Claim")
			doc = frappe.get_doc('Invoice Recognition', name[0].get('name'))
			employee = doc.employee
			expense_claim.employee = employee

			company = doc.company
			expense_claim.company = company
			expense_claim.project = name[0].get('project')
			department = frappe.db.get_value('Employee', employee, 'department')
			if department:
				expense_approver = frappe.db.get_value(
					"Department Approver",
					{"parent": department, "parentfield": "expense_approvers", "idx": 1},
					"approver",
				)
				expense_claim.expense_approver = expense_approver

			default_payable_account = frappe.get_cached_value(
				"Company", company, "default_expense_claim_payable_account"
			)

			expense_claim.payable_account = default_payable_account

			default_cost_center = frappe.get_cached_value("Company", company, "cost_center")
			expense_claim.cost_center = default_cost_center

			# 附加报销信息
			for ir in name:
				account = frappe.db.get_value(
					"Expense Claim Account", {"parent": ir.get('expense_type'), "company": company}, "default_account"
				)

				expenses = {
						"expense_date": today(),
						"expense_type": ir.get('expense_type'),
						"amount": ir.get('grand_total'),
						"invoice_recognition": ir.get('name'),
						"cost_center": default_cost_center,
						"default_account":account,
					}
				expense_claim.append(
					"expenses",expenses,
				)
			expense_claim.save(ignore_permissions=True)
			return expense_claim

def validate_ir_list(name_list):
	companys = list(set([d.get('company') for d in name_list]))
	if len(companys) > 1:
		frappe.throw('发票归属于不同公司，无法批量创建报销单')

	projects = list(set([d.get('project') for d in name_list]))
	if len(projects) > 1:
		frappe.throw('发票归属于不同项目，无法批量创建报销单')

	employees = list(set([d.get('employee') for d in name_list]))
	if len(employees) > 1:
		frappe.throw('发票归属于不同员工，无法批量创建报销单')

@frappe.whitelist()
def get_invoice_recognition(company,employee,project=None):
	filters = {
		'company': company,
		'employee': employee, 
		'status': 'Recognized'
	}
	if project:
		filters['project'] = project

	fields = ('name','invoice_date','party','expense_type','invoice_type_org','invoice_code','invoice_num','total_tax','grand_total','attach','project','company','employee')
	ir_list = frappe.get_list('Invoice Recognition', filters=filters,fields=fields)

	return ir_list

@frappe.whitelist()
def update_employee(docname, employee):
	doc = frappe.get_doc('Invoice Recognition', docname)
	doc.flags.ignore_validate_update_after_submit = True
	doc.employee = employee
	doc.save(ignore_permissions=True)
	doc.flags.ignore_validate_update_after_submit = False
	return {'employee':employee}

@frappe.whitelist()
def re_recognize(docname):
	doc = frappe.get_doc('Invoice Recognition', docname)
	doc.flags.ignore_validate_update_after_submit = True
	doc.get_invoice_info(re_recognize=True)
	doc.save(ignore_permissions=True)
	doc.flags.ignore_validate_update_after_submit = False