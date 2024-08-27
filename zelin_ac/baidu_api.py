import frappe
import base64
import cv2
import json
import mimetypes
import numpy as np  
import os
from PIL import Image
import requests
import urllib.parse
import shutil


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

    #装了cloud_storage后，file_url长这样 /api/method/retrieve?key=erpnext/Item/A/上传.pdf    
    if file_url[:5] == '/api/':
        from cloud_storage.cloud_storage.overrides.file import get_file_stream

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

@frappe.whitelist()
def get_invoice_rep(invoice_upload):
    #frappe.msgprint(invoice_upload)
    base_dir = frappe.get_site_path()
    base_path = base_dir + "/public"

    if(invoice_upload[:6] == "/files"):
        input_image_path = base_dir + "/public" + invoice_upload
    else:
        input_image_path = invoice_upload
    #图片预处理至小于4M
    base_file_path = os.path.basename(input_image_path)
    output_image_path = base_dir + "/public/files/reget/" + base_file_path
    max_file_size = 6 * 1024 * 1024  # 3MB
    if(os.path.getsize(input_image_path) > max_file_size):
       scale_factor = 0.8  # 缩放因子
       # 打开输入图像
       input_image = Image.open(input_image_path)
       # 初始化缩放比例
       max_attempts = 10  # 最大尝试次数
       scale = 1.0
       attempt = 0
       while attempt < max_attempts:
           # 缩放图像
           scaled_image = input_image.resize((int(input_image.width * scale) , int(input_image.height * scale)) ,
                                             Image.ANTIALIAS)
           # 保存缩放后的图像
           scaled_image.save(output_image_path , "PNG")
           # 获取输出文件大小
           output_size = os.path.getsize(output_image_path)
           if output_size <= max_file_size:
               if os.path.exists(input_image_path):
                  os.remove(input_image_path)
               shutil.copy(output_image_path , input_image_path)
               break
           # 更新缩放比例
           scale *= scale_factor
           attempt += 1
       if attempt>=10:
          frappe.throw("转化的图片过大,无法压缩,请检查上传文件！")
    # 采用文心一言百度模型识别票据信息。    
    baidu_settings = frappe.get_single('Baidu Settings')
    API_KEY = baidu_settings.api_key
    SECRET_KEY = baidu_settings.get_password(fieldname="secret_key", raise_exception=False)

    access_token = get_baidu_access_token(API_KEY, SECRET_KEY)
    if not access_token:
        frappe.throw('获取百度智能云接口API access_token失败，请联系系统管理员')
        return

    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token=" + access_token
    # 二进制方式打开图片文件
    f = open(input_image_path , 'rb')
    img = base64.b64encode(f.read())
    params = {"image": img,
              "detect_direction": "true"
              }
    headers = {'Content-Type': 'application/x-www-form-urlencoded' , 'Accept': 'application/json'}

    response = requests.request("POST" , url , headers=headers , data=params)
    data = json.loads(response.text)
    words_result = data.get('words_result')
    if not words_result:
        frappe.msgprint(f"调用百度接口api失败，错误消息 {data.get('error_msg')}")
        return
    #图片视图方向处理
    if data['direction'] != 0:
        run_picture_spin(input_image_path , data['direction'] * 90)
    #图片结果处理
    
    words_list = [item['words'].replace(':' , '：') for item in words_result]
    words_string = ', '.join(words_list)
    words_string = words_string.replace(':', '：')
    return words_string


def run_picture_spin(picture_path, angle):
    base_dir = frappe.get_site_path()
    img = cv2.imread(picture_path)
    height = img.shape[0]  # 图片的高度、图片的垂直尺寸
    width = img.shape[1]  # 图片的宽度、图片的水平尺寸
    channel = img.shape[2]  # 通道
    img1 = None
    if angle == 90:  # 右旋90°
        img1 = np.zeros([width, height, channel], np.uint8)
        for row in range(height):
            img1[:, height - row - 1, :] = img[row, :, :]
    elif angle == 270:  # 左旋转90° 右旋270°
        img1 = np.zeros([width, height, channel], np.uint8)
        for row in range(height):
            img1[:, row, :] = img[row, :, :]
        img1 = img1[::-1]
    elif angle == 180:  # 旋转180°
        temp = img[::-1]
        img1 = np.zeros([height, width, channel], np.uint8)
        for col in range(width):
            img1[:, width - col - 1, :] = temp[:, col, :]
    elif angle == -180:  # 垂直翻转180°
        img1 = img[::-1]
    elif angle == -90:  # 水平翻转90°
        img1 = np.zeros([height, width, channel], np.uint8)
        for col in range(width):
            img1[:, width - col - 1, :] = img[:, col, :]

    new_img_path = os.path.join(base_dir, "public/files/reget/re0.png")  
    
    # 确保 reget 目录存在  
    reget_dir = os.path.dirname(new_img_path)  
    os.makedirs(reget_dir, exist_ok=True)  
    
    # 使用 cv2.imencode 将图像编码为 PNG 格式，并写入文件  
    _, encoded_img = cv2.imencode('.png', img1)  # 确保 img1 已经定义  
    
    # 将编码后的图像字节写入文件  
    with open(new_img_path, 'wb') as f:  
        f.write(encoded_img.tobytes())  
 
    if os.path.exists(picture_path):  
        os.remove(picture_path)  
    
    # 移动新生成的文件到目标路径  
    shutil.move(new_img_path, picture_path)


def get_baidu_access_token(API_KEY, SECRET_KEY):
    """
    使用 AK,SK 生成鉴权签名(Access Token) return: access_token,或是None(如果错误)
    """

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}
    access_token = str(requests.post(url, params=params).json().get("access_token"))
    
    return access_token