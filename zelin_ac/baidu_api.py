import base64  
import urllib.parse
import requests
import json
import frappe
import mimetypes

@frappe.whitelist()
def get_invoice_info(file_url):

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

	payload= file_type +  file_to_base64_and_urlencode('./' + frappe.local.site + file_url) +'&verify_parameter=false&probability=false&location=false'
	url = "https://aip.baidubce.com/rest/2.0/ocr/v1/multiple_invoice?access_token=" + access_token

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