import base64  
import urllib.parse
import requests
import json
import frappe
import mimetypes


invoice_type_map ={
	'电子发票(专用发票)':'elec_special_vat_invoice'
}

@frappe.whitelist()
def vat_invoice_verification(doc):
	'''OCR-增值税发票验真'''

	baidu_settings = frappe.get_single('Baidu Settings')
	API_KEY = baidu_settings.api_key
	SECRET_KEY = baidu_settings.get_password(fieldname="secret_key", raise_exception=False)
	access_token = get_baidu_access_token(API_KEY, SECRET_KEY)
	if not access_token:
		frappe.throw('获取百度智能云接口API access_token失败，请联系系统管理员')
		return
	
	url = "https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice_verification?access_token=" + access_token
	params = {f:doc.get(f) for f in 
		["check_code","invoice_code","invoice_date","invoice_num","invoice_type","total_amount"] if doc.get(f)}
	invoice_type = params['invoice_type']
	params['invoice_type'] = invoice_type_map.get(invoice_type, invoice_type)
	params['invoice_date'] = ''.join(params['invoice_date'].replace('年', '').replace('月', '').replace('日', '')) 
	#params = {"check_code":"校验码。填写发票校验码后6位","invoice_code":"发票代码","invoice_date":"开票日期","invoice_num":"发票号码","invoice_type":"发票类型","total_amount":"不含税金额"}	
	headers = {'content-type': 'application/x-www-form-urlencoded'}
	response = requests.post(url, data=params, headers=headers)
	if response:
		print (response.json())

@frappe.whitelist()
def get_invoice_info(file_url):
	from cloud_storage.cloud_storage.overrides.file import get_file_stream

	file_type = mimetypes.guess_type(file_url)[0]

	if file_type == 'application/pdf':
		file_type = 'pdf_file='
	elif file_type in ('image/jpeg', 'image/png', 'image/jpg'):
		file_type = 'image='

	baidu_settings = frappe.get_single('Baidu Settings')
	API_KEY = baidu_settings.api_key
	SECRET_KEY = baidu_settings.get_password(fieldname="secret_key", raise_exception=False)

	access_token = get_baidu_access_token(API_KEY, SECRET_KEY)
	if not access_token:
		frappe.throw('获取百度智能云接口API access_token失败，请联系系统管理员')
		return
	
	url = "https://aip.baidubce.com/rest/2.0/ocr/v1/multiple_invoice?access_token=" + access_token

	#将了cloud_storage后，file_url长这样 /api/method/retrieve?key=erpnext/Item/A/上传.pdf	
	if file_url[:5] == '/api/':
		headers = {
			'Content-Type': 'application/x-www-form-urlencoded',
			'Accept': 'application/json'
		}
		file_name, s3_key = frappe.db.get_value('File', {'file_url': file_url}, ['file_name','s3_key'])
		file_stream = get_file_stream(s3_key)
		params = {"image":file_stream}
		file_type='image' if file_type == 'image=' else 'pdf'
		files = {file_type: (file_name or file_url, file_stream, mimetypes.guess_type(file_url)[0])}  # 注意：这里的'filename.jpg'是文件名，可以自定义  
		response = requests.request("POST", url, data=params, headers=headers)
	else:
		payload= file_type +  file_to_base64_and_urlencode('./' + frappe.local.site + file_url) +'&verify_parameter=false&probability=false&location=false'
		headers = {
			'Content-Type': 'application/x-www-form-urlencoded',
			'Accept': 'application/json'
		}
		response = requests.request("POST", url, headers=headers, data=payload)
	baidu_settings.call_count = (baidu_settings.call_count or 0) + 1
	baidu_settings.save(ignore_permissions=1)
	# print(response.text)
	return response.text
	
def file_to_base64_and_urlencode(pdf_file_path):  
	# 读取PDF文件  
	with open(pdf_file_path, 'rb') as pdf_file:  
		pdf_content = pdf_file.read()  

	# 将PDF内容编码为base64字符串  
	base64_bytes = base64.b64encode(pdf_content)  
	base64_str = base64_bytes.decode('utf-8')  

	# 如果需要进行URL编码（通常不需要）  
	url_encoded_str = urllib.parse.quote_plus(base64_str)  

	# 返回base64字符串（或URL编码后的字符串，如果需要）  
	# return base64_str  # 或者返回 url_encoded_str  
	return url_encoded_str

def get_baidu_access_token(API_KEY, SECRET_KEY):
	"""
	使用 AK,SK 生成鉴权签名(Access Token)
	:return: access_token,或是None(如果错误)
	"""
	# API_KEY = 'RAVZNLLiUky0f7bpzWCo4xa8'
	# SECRET_KEY = '2rLk5ni0eZFaaSF1hftJt7viXo2O6KJL'
	url = "https://aip.baidubce.com/oauth/2.0/token"
	params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}
	access_token = str(requests.post(url, params=params).json().get("access_token"))
	# baidu_settings.access_token = access_token
	# baidu_settings.save()
	
	return access_token