# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
import frappe
from frappe.utils import flt, random_string
import base64
import requests
import os
import fitz  # PyMuPDF库
from PIL import Image    #用于多页pdf 合并png
import json
import shutil
import re
import time
from zelin_ac.baidu_api import get_invoice_rep

e_invoice_types =[
    '电子发票',
    '电子普通发票',
    '电子专用发票',
    '电子票据‌',
    '全电发票'
]

class MyInvoice(Document):
    def validate(self):
        self.set_employee()

    def set_employee(self):
        if not self.employee:
            self.employee = frappe.db.get_value('Employee', {'user_id': self.owner_user})

    def on_trash(self):
        if self.status == "已使用":
            frappe.throw("不允许删除已经被使用的发票！")
            return
        if self.files:    
            base_dir = frappe.get_site_path()
            file_path = os.path.join(base_dir, 'public' + self.files)
            if os.path.exists(file_path):
                os.remove(file_path)

@frappe.whitelist()
def upload_invoices(filename, filedata):
    def parse_and_save_my_invoice(myinvoice):
        res_uploadfilename = os.path.relpath(save_path, base_path)
        res_upload = '/' + res_uploadfilename
        myinvoice.files = res_upload
        words_string = get_invoice_rep(res_upload)
        myinvoice.rep_txt = words_string        
        if file_extension not in ['.PDF' , '.pdf'] and any(txt in words_string for txt in e_invoice_types):
            frappe.msgprint(f'未能上传 {filename}，电子发票只支持pdf格式')
            myinvoice.delete(ignore_permissions=1, force=1)
        elif words_string.count('仅供') > 1:
            frappe.msgprint(f"未能上传 {filename}，系统只支持一个文件一张火车票")
            os.remove(save_path)
            myinvoice.delete(ignore_permissions=1, force=1)
        else:
            myinvoice.save()
            created_invoices.append(myinvoice.name)
            if words_string:
                get_invoice_code(myinvoice.name, "My Invoice")
            return True

    doctype= "My Invoice"
    base_dir = frappe.get_site_path()
    # 保存文件到 public/invoice_upload 目录
    upload_dir = os.path.join(base_dir , 'public/files/My Invoice/all_upload')
    user = frappe.get_user()
    username = frappe.db.get_value('User', user.name, 'first_name')
    save_dir = os.path.join(base_dir , 'public/files/' + doctype, username)
    if not os.path.exists(upload_dir) :
        os.makedirs(upload_dir)
    if not os.path.exists(save_dir) :
        os.makedirs(save_dir)
        # 分割文件名和扩展名
    file_name, file_extension = os.path.splitext(filename)
    if file_extension not in ['.PDF', '.pdf', '.PNG', '.png', '.JPG', '.jpg'] :
        frappe.throw(f"未能上传 {filename}，系统只支持PDF、PNG、JPG三种格式的文件上传！")

    created_invoices = []
    upload_path = os.path.join(upload_dir, f"{file_name}-{random_string(6)}{file_extension}")
    base_path = base_dir + "/public"
    res_uploadfilename = os.path.relpath(upload_path , base_path)
    res_upload = '/' + res_uploadfilename
    filedata = base64.b64decode(filedata.split('base64,')[1])
    with open(upload_path, 'wb') as f :
        f.write(filedata)
    if file_extension.lower() in ['.pdf'] :
        pdf_file_path = os.path.abspath(upload_path)
        pdf_document = fitz.open(pdf_file_path)

        if pdf_document.page_count > 1:
            #多页pdf, 一个发票多页的情况
            page_0_inv_num = get_inv_num_from_pdf_page(pdf_document, 0)
            page_1_inv_num = get_inv_num_from_pdf_page(pdf_document, 1)
            if page_0_inv_num and page_1_inv_num and page_0_inv_num == page_1_inv_num:
                myinvoice = get_new_myinvoice(user.name,filename)
                docname = myinvoice.name
                png_filename = f"{docname}-{random_string(6)}.png"
                save_path = os.path.join(save_dir, png_filename)                                
                multi_page_pdf_to_png(pdf_document, save_dir, png_filename)
                parse_and_save_my_invoice(myinvoice)
        else:   #多页pdf,每页一个发票
            for page_number in range(pdf_document.page_count) :
                myinvoice = get_new_myinvoice(user.name,filename)
                docname= myinvoice.name
                dpi = 150  # 200 DPI，可以根据需要调整
                page = pdf_document.load_page(page_number)
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72 , dpi / 72))
                png_filename = f"{docname}-{random_string(6)}.png"
                save_path = os.path.join(save_dir, png_filename)
                pix.save(save_path, "png")
                parse_and_save_my_invoice(myinvoice)
    else:
        myinvoice = get_new_myinvoice(user.name,filename)
        docname = myinvoice.name
        png_filename = f"{docname}-{random_string(6)}{file_extension}"
        save_path = os.path.join(save_dir, png_filename)
        shutil.copy(upload_path, save_path) 
        parse_and_save_my_invoice(myinvoice)

    return created_invoices

def multi_page_pdf_to_png(pdf_document, save_dir, png_filename, dpi=150):
    images = []  # List to store individual PNG images
    for page_number in range(pdf_document.page_count):
        page = pdf_document.load_page(page_number)
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        file_path = os.path.join(save_dir, f"{png_filename}_{page_number}.png") 
        pix.save(file_path, "png")     
        images.append(Image.open(file_path))  # Load PNG into PIL Image
        if os.path.exists(file_path):
            os.remove(file_path)
    # Combine PNG images vertically (top to bottom)
    first_image = images[0]
    combined_image = Image.new(first_image.mode, (first_image.width, sum(image.height for image in images)))
    y_offset = 0
    for image in images:
        combined_image.paste(image, (0, y_offset))
        y_offset += image.height
    file_path = os.path.join(save_dir, png_filename)    
    combined_image.save(file_path, "png")

def get_inv_num_from_pdf_page(pdf_document, page_number):
    page = pdf_document.load_page(page_number)
    text = page.get_text("words")  # 获取页面文本内容
    left, top, right, bottom = 0, 0, 0, 0
    for row in text:
        if '发票号码：' == row[4]:
            left, top, right, bottom = row[:4]
            break
    if top and right and bottom:
        for row in text:
            if row[0] > right and row[2] < (right + 100) and top < (row[1] + row[3])/2 < bottom:
                return row[4]

def get_new_myinvoice(user_name, description) :
    myinvoice = frappe.new_doc("My Invoice")
    myinvoice.update(
        {
            "invoice_type" : "其他",
            "description": description,
            "owner_user" : user_name,
        }
    )
    myinvoice.save()
    return myinvoice

@frappe.whitelist()
def upload_file(docname , doctype , filename , filedata) :
    base_dir = frappe.get_site_path()
    # 保存文件到 public/invoice_upload 目录
    user = frappe.get_user()
    upload_dir = os.path.join(base_dir , 'public/files/' + doctype , user.name)
    if not os.path.exists(upload_dir) :
        os.makedirs(upload_dir)
    # 分割文件名和扩展名
    file_name , file_extension = os.path.splitext(filename)
    if file_extension not in ['.PDF' , '.pdf' , '.PNG' , '.png' , '.JPG' , '.jpg'] :
        frappe.throw("仅支持PDF、PNG、JPG三种格式的文件上传！")
    new_filename = f"{docname}{file_extension}"
    upload_path = os.path.join(upload_dir , new_filename)
    base_path = base_dir + "/public"
    res_uploadfilename = os.path.relpath(upload_path , base_path)
    res_upload = '/' + res_uploadfilename
    filedata = base64.b64decode(filedata.split('base64,')[1])
    with open(upload_path , 'wb') as f :
        f.write(filedata)
    if file_extension.lower() in ['.pdf'] :
        pdf_file_path = os.path.abspath(upload_path)
        pdf_document = fitz.open(pdf_file_path)
        # 设置分辨率
        dpi = 150  # 200 DPI，可以根据需要调整
        if pdf_document.page_count > 1 :
            frappe.msgprint("仅支持上传显示PDF第一页，如需转换所有页面，请在本地转换后上传。")
        page_number = 0
        page = pdf_document.load_page(page_number)
        # 设置分辨率
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72 , dpi / 72))
        # pix = page.get_pixmap()
        png_file_path = pdf_file_path.replace(".pdf" , "").replace(".PDF" , "")
        png_filename = f"{png_file_path}.png"
        pix.save(png_filename , "png")
        # frappe.msgprint(f"PDF的第一页已转换为PNG并保存为{png_filename}。")
        upload_path = os.path.join(upload_dir , png_filename)
        res_uploadfilename = os.path.relpath(upload_path , base_path)
        res_upload = '/' + res_uploadfilename
    doc = frappe.get_doc(doctype , docname)
    doc.files = res_upload
    words_string = get_invoice_rep(res_upload)
    doc.rep_txt = words_string
    doc.save()
    get_invoice_code(doc.name,doctype)

@frappe.whitelist()
def get_invoice_code(docname, doctype) :
    doc = frappe.get_doc(doctype , docname)
    if not doc.files:
        return

    doc.reload()
    res_upload = doc.files
    if not doc.rep_txt:
        words_string = get_invoice_rep(res_upload)
        doc.rep_txt = words_string
    else:
        words_string = doc.rep_txt
    if not words_string:
        return    
    words_list = words_string.split(', ')
    words_list = [word.replace(",","") for word in words_list]
    setting = frappe.get_doc("Invoice Type Setting")
    invoice_type = "其他"
    # 遍历InvoiceTypeSetting中的每个关键字项
    for item in setting.keywords:
        # 解析关键字定义
        keyword_definitions = item.keyword.split(';')
        globals().update(locals())
        required_keywords = [kw.split(',')[0] for kw in keyword_definitions if len(kw.split(','))>1 and kw.split(',')[1] == '1']
        optional_keywords = [kw.split(',')[0] for kw in keyword_definitions if len(kw.split(','))>1 and kw.split(',')[1] == '0']
        if not (required_keywords or optional_keywords):
            continue
        print(item.idx, item.invoice_type, item.keyword, required_keywords, optional_keywords)
        # 检查是否满足所有必需关键字和没有任何可选关键字        
        if all(kw in words_string for kw in required_keywords) and not any(kw in words_string for kw in optional_keywords):
            # 返回对应的发票类型
            invoice_type = item.invoice_type
            break

    invoice_code = ''
    net_amount = 0
    tax_amount = 0
    inco_f = ""
    inco_b = ""

    if '纳税人识别号' in words_string or '发票号码' in words_string or '发票代码' in words_string or '票据' in words_string or ('发票' in words_string and '代码' in words_string) or '税收完税证明' in words_string:
        if ('发票代码' in words_string and '发票号码' in words_string) or ('发票代码' not in words_string and '发票号码' not in words_string and '票据' not in words_string and '税收完税证明' not in words_string):
            for word in words_list:
                word_daw = re.sub(r'[发票代号码：]', '', word)
                if '发票代码' in word and not inco_f:
                    if re.match("^[a-zA-Z0-9]+$" ,re.sub(r'[^\w]' , '' , word_daw)) and re.search(r'\d', word_daw):
                        inco_f = word_daw
                elif re.match("^[a-zA-Z0-9]+$" ,re.sub(r'[^\w]' , '' , word_daw)) and re.search(r'\d', word_daw) and (len(word_daw) >= 10 and  len(word_daw) <= 12) and not inco_f and not re.search(r'[-#$*]', word_daw):
                    inco_f = word_daw
                elif '发票号码' in word and not inco_b:
                    if re.match("^[a-zA-Z0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) :
                        inco_b = word_daw
                elif re.match("^[0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) and len(word_daw)==8 and not inco_b :
                    inco_b = word_daw
            if inco_f and inco_b :
                invoice_code = inco_f + "_" + inco_b
        elif '发票代码' not in words_string and '发票号码' in words_string and '纳税人识别号' in words_string:

            for word in words_list :
                word_daw = re.sub(r'[数电发票代号码：]', '', word)
                if '发票号码' in word and not inco_f :
                    if re.match("^[0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) :
                        inco_f = word_daw
                elif re.match("^[0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) and len(word_daw) >= 20 and not inco_f :
                    inco_f = word_daw
                invoice_code = inco_f
        elif '票据' in words_string :

            for word in words_list:
                word_daw = re.sub(r'[票据代号码：]', '', word)
                if '票据号码' in word and not inco_f:
                    if re.match("^[0-9]+$" ,re.sub(r'[^\w]' , '' , word_daw)):
                        inco_f = word_daw
                elif re.match("^[0-9]+$" ,re.sub(r'[^\w]' , '' , word_daw)) and (len(word_daw) >= 10 and  len(word_daw) <= 12) and not inco_f:
                    inco_f = word_daw
                elif '票据代码' in word and not inco_b:
                    if re.match("^[0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) :
                        inco_b = word_daw
                elif re.match("^[0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) and len(word_daw)==8 and not inco_b :
                    inco_b = word_daw
            if inco_f and inco_b :
                invoice_code = inco_f + "_" + inco_b
        elif "税收完税证明" in words_string:
            for word in words_list:
                word_daw = word.replace('No.','')
                if 'No.' in word and not inco_f:
                    inco_f = word_daw
            if inco_f :
                invoice_code = inco_f
        else:
            for word in words_list :
                word_daw = re.sub(r'[发票代号码：]', '', word)
                if '发票代码' in word and not inco_f :
                    if re.match("^[a-zA-Z0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) and re.search(r'\d' , word_daw) :
                        inco_f = word_daw
                elif re.match("^[a-zA-Z0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) and re.search(r'\d' , word_daw) and (len(word_daw) >= 10 and len(word_daw) <= 12) and not inco_f :
                    inco_f = word_daw
                elif '发票号码' in word and not inco_b :
                    if re.match("^[a-zA-Z0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) :
                        inco_b = word_daw
                elif re.match("^[0-9]+$" , re.sub(r'[^\w]' , '' , word_daw)) and len(word_daw) == 8 and not inco_b :
                    inco_b = word_daw
            if inco_f and inco_b :
                invoice_code = inco_f + "_" + inco_b
            elif inco_f and not inco_b :
                invoice_code = inco_f
            elif not inco_f and inco_b :
                invoice_code = inco_b

    if not invoice_code:
        if invoice_type == '飞机票' :
            filtered_list = [word for word in words_list if len(word) == 11 and word.isdigit()]
            if filtered_list :
                invoice_code = filtered_list[0]
        elif invoice_type == '火车票' :
            filtered_list = [word for word in words_list if len(word) >= 6 and len(word) <= 12 and (word.isalnum()  and word.isupper() or word.isdigit()) and not re.search(r'[\u4e00-\u9fa5]', word)]
            if filtered_list :
                invoice_code = filtered_list[0]
        elif invoice_type == '其他' :
            filtered_list = [word for word in words_list if len(word) >= 6 and len(word) <= 12 and (word.isalnum()  and word.isupper() or word.isdigit()) and not re.search(r'[\u4e00-\u9fa5]', word)]
            if filtered_list :
                invoice_code = filtered_list[0]

    # 优先根据关键字定位而不是只获取像金额的数字，通过比大小来识别                
    if any(txt in words_string for txt in ['普通发票', '专用发票']):
        set_amount(doc)

    amount_list = []
    if not (doc.amount and doc.net_amount):
        if 'CNY' in words_string and float(net_amount) == 0:
            for amount in words_list:
                if re.search(r'^[^.]*\.\d{1,2}(?:[^.]*\.\d{1,2})?$', amount) and not re.search(r'\..*?\..+', amount):
                    amount_value = re.sub(r'[^0-9.]', '', amount)
                    if float(amount_value) > 0 and float(amount_value) < 100000:
                        amount_list.append(float(amount_value))
                elif re.search( r'^CNY(?:[CNY\d]*\.\d+|\d+(?:\.\d+)?)[CNY\d]*$', amount) and not re.search(r'\..*?\..+', amount):

                    amount_value = re.sub(r'[^0-9.]' , '' , amount)
                    if float(amount_value) > 0 and float(amount_value) < 100000:
                        amount_list.append(float(amount_value))
            sorted_amounts = sorted(amount_list,reverse=True)
            if len(sorted_amounts) >= 1 :
                net_amount = sorted_amounts[0]
        if '￥' in words_string and float(net_amount) == 0:
            for amount in words_list:
                if '￥' in amount and re.search(r'\d+(\.\d+)?', amount) and not re.search(r'\..*?\..+', amount):
                    amount_value = re.sub(r'[^0-9.]', '', amount)
                    if float(amount_value) > 0 and float(amount_value) < 100000:
                        amount_list.append(float(amount_value))
            sorted_amounts = sorted(amount_list)
            if len(sorted_amounts) > 1 :
                net_amount = sorted_amounts[1]
                if sorted_amounts[0] < 0.2*net_amount:
                    tax_amount = sorted_amounts[0]
            elif len(sorted_amounts) == 1 :
                net_amount = sorted_amounts[0]
        if '元' in words_string and float(net_amount) == 0:
            for amount in words_list:
                if '元' in amount and re.search(r'\d+(\.\d+)?', amount) and '/' not in amount and not re.search(r'\..*?\..+', amount):
                    amount_value = re.sub(r'[^0-9.]', '', amount)
                    if float(amount_value) > 0 and float(amount_value) < 100000:
                        amount_list.append(float(amount_value))
            sorted_amounts = sorted(amount_list)
            if len(sorted_amounts) > 1 :
                net_amount = sorted_amounts[1]
                if sorted_amounts[0] < 0.2*net_amount:
                    tax_amount = sorted_amounts[0]
            elif len(sorted_amounts) == 1 :
                net_amount = sorted_amounts[0]
        if float(net_amount) == 0:
            for amount in words_list:
                if re.fullmatch(r'^\d+(,\d+)*(\.\d{1,2})$' , amount) and not re.search(r'\..*?\..+', amount):
                    amount_value = re.sub(r'[^0-9.]' , '' , amount)
                    if float(amount_value) > 0 and float(amount_value) < 100000:
                        amount_list.append(float(amount_value))
            sorted_amounts = sorted(amount_list)
            if len(sorted_amounts) > 1 :
                net_amount = sorted_amounts[1]
                if sorted_amounts[0] < 0.2*net_amount:
                    tax_amount = sorted_amounts[0]
            elif len(sorted_amounts) == 1 :
                net_amount = sorted_amounts[0]
    if invoice_code:
        parent_value = get_db_invoice(docname, invoice_code)
        if parent_value:
            frappe.msgprint(f"{invoice_code}: 此发票已经在单据 {parent_value} 中存在,已经使用的发票无法再次上传，已经剔除本次重复发票！")
            frappe.delete_doc(doctype, docname, ignore_permissions = True, force = 1)
            return

    doc.invoice_type = invoice_type
    if not (doc.amount and doc.net_amount) and net_amount:
        doc.net_amount = net_amount
        doc.tax_amount = tax_amount
        doc.amount = net_amount + tax_amount
    doc.invoice_code = invoice_code
    if invoice_type in ['火车票', '飞机票', '通行费']:
        set_ticket_owner(doc)
    set_invoice_date(doc)
    tax_rate_map = frappe._dict(frappe.get_all('My Invoice Type', fields=['name','deductible_tax_rate'], as_list=1))
    doc.is_special_vat = 1 if any(s in doc.rep_txt for s in ["增值税专用发票"]) else 0  
    set_deductible_tax_amount(doc, tax_rate_map)
    set_company(doc)
    if not doc.amount:
        doc.status = '不能使用'
        doc.error_message = "未识别出发票金额，非发票文件?"      
    doc.save()

def set_amount(doc):
    text = doc.rep_txt
    pattern = r'[（\(]小写[）\)]\s*(?:[，,]?\s*￥\s*)?(\d+(\.\d+)?)'  #类似这种 (小写), ￥49910.60, 
    match = re.search(pattern, text)  
    if match:  
        number = match.group(1)  # 提取并打印数字部分  
        doc.amount = number

    pattern = r'计[\s,]*￥(\d+(\.\d+)?)[\s,]*￥(\d+(\.\d+)?)[\s,]*价'  
    match = re.search(pattern, text)  
    if match:  
        if len(match.groups()) > 3:
            doc.net_amount = match.group(1)
            doc.tax_amount = match.group(3)

def set_ticket_owner(doc):
    name_match = re.search(r'\*\*(\d{4})\s*?(.*?)(,|$)', doc.rep_txt)  
    if name_match:  
        doc.ticket_owner = name_match.group(2).strip()
        employee = frappe.db.get_value('Employee', {'first_name': doc.ticket_owner})
        if employee:
            doc.employee = employee
            doc.is_employee = 1

def set_invoice_date(doc):
    patterns =[r'开票日期：(\d{4}年\d{2}月\d{2}日)', r'(\d{4}年\d{2}月\d{2}日)']
    for pattern in patterns:
        match = re.search(pattern, doc.rep_txt)    
        if match:  
            date_str = match.group(1).replace('年', '').replace('月', '').replace('日', '')  
            date_yyyymmdd = date_str.replace(' ', '')  
            doc.invoice_date = date_yyyymmdd
            return

def set_deductible_tax_amount(doc, tax_rate_map):
    if doc.is_special_vat and doc.tax_amount:
        doc.deductible_tax_amount = flt(doc.tax_amount)
        if doc.net_amount and doc.tax_amount:
            doc.tax_rate = flt(doc.tax_amount / flt(doc.net_amount) * 100, 0)            
    elif not doc.ticket_owner or (doc.ticket_owner and doc.is_employee):
        # 国内机票扣除代收不征税项外，可9% 抵扣
        base_amount = flt(doc.amount)
        tax_rate = tax_rate_map.get(doc.invoice_type, 0) / 100
        text = doc.rep_txt
        if "国内机票款" in text:
            pattern = r'(\d+(?:\.\d+)?)(?=,\s*不征税)'
            match = re.search(pattern, text)
            if match:
                untaxed_amt = match.group(1)
                base_amount -= flt(untaxed_amt)
                tax_rate = 0.09
        if tax_rate:
            doc.tax_rate = tax_rate * 100
            # 计算公式：火车票可抵扣进项税 = 票面金额 ÷ (1 + 9%) × 9%。
            doc.deductible_tax_amount = base_amount / (1 + tax_rate) * tax_rate
    

def set_company(doc):
    #“购买方, 纳税人识别号：”和紧接着的逗号之间的文本串
    patterns = [r'购买方, 纳税人识别号：([^,]+)', r'统一社会信用代码/纳税人识别号：([^,]+)']
    for pattern in patterns:
        match = re.search(pattern, doc.rep_txt)    
        if match:  
            company_tax_id = match.group(1)                           
            company = frappe.db.get_value('Company', {'tax_id': company_tax_id})
            if company:
                doc.company_code = company
            else:
                doc.status = '不能使用'
                doc.error_message = f'非系统内公司税号: {company_tax_id}'
            return   #如果匹配到了就返回 

@frappe.whitelist()
def get_invoice_codes(docnames) :
    docnames = json.loads(frappe.form_dict['docnames'])
    for name in docnames :
        get_invoice_code(name,"My Invoice")
    frappe.msgprint("获取 %s 发票" % len(docnames))

@frappe.whitelist()
def get_db_invoice(docname,invoice_code):
    # 查询 invoice_upload 子表中与指定 expenses 子表行相关的行数据
    query = """
        SELECT name  -- 将你需要的字段列在这里
        FROM `tabMy Invoice`
        WHERE name != %s and invoice_code = %s
    """
    files = frappe.db.sql(query, (docname,invoice_code,), as_dict=True)
    # 将文件列表中的字符串连接成一个字符串
    #file_strings = ", ".join([file.get("parent") for file in files])
    #frappe.msgprint("重复单号：" + file_strings)
    return files

@frappe.whitelist()
def expense_select_invoice(docname, expense_claim_item, items):
    items = json.loads(items).get("items")    
    if expense_claim_item == "选择发票生成报销明细":
        my_invoice_list = [r.get('name') for r in items]
        my_inv = frappe.qb.DocType('My Invoice')
        my_inv_type = frappe.qb.DocType('My Invoice Type')

        data = frappe.qb.from_(my_inv
        ).left_join(my_inv_type
        ).on(my_inv.invoice_type == my_inv_type.name
        ).where(my_inv.name.isin(my_invoice_list)
        ).select(
            my_inv.name.as_('my_invoice'),
            my_inv_type.expense_type,
            my_inv.deductible_tax_amount,
            my_inv.amount,
            my_inv.amount.as_('my_invoice_amount'),
            my_inv.amount.as_('sanctioned_amount'),
            my_inv.is_special_vat,
            my_inv.description,
            my_inv.invoice_code
        ).run(as_dict=1)
        
        expense_claim_doc = frappe.get_doc('Expense Claim', docname)
        for d in data:
            if not d.expense_type and expense_claim_doc.default_expense_type:
                d.expense_type = expense_claim_doc.default_expense_type    
            d.expense_date = frappe.utils.getdate()  
            expense_claim_doc.append('expenses', d)                

        if (any(row for row in expense_claim_doc.expenses if not row.expense_type) and
            not expense_claim_doc.default_expense_type):
            frappe.throw("请先在发票类型中维护报销类型或在报销单上选择默认报销类型")
            return

        expense_claim_doc.total_my_invoice_amount = sum(d.my_invoice_amount for d in data)
        expense_claim_doc.save(ignore_permissions=1)

        #更新我的发票中的报销单号与状态
        rows = [d for d in expense_claim_doc.expenses if d.my_invoice and d.my_invoice in my_invoice_list]
        for expense_row in rows:            
            frappe.db.set_value('My Invoice', expense_row.my_invoice, 
                {
                    'expense_claim': expense_claim_doc.name,
                    'expense_claim_item': expense_row.name,
                    'status': "已使用"
                }
            )
    else:        
        for row in items:
            my_invoice =  row.get('name')
            frappe.db.sql("""
                UPDATE `tabMy Invoice`
                SET expense_claim = %s, expense_claim_item = %s,status = %s
                WHERE name = %s
            """, (docname, expense_claim_item, "已使用", my_invoice))

            update_expense_item_my_invoice_amount(docname)

@frappe.whitelist()
def expense_remove_invoice(row_values, docname) :
    data_values = frappe.parse_json(row_values)
    my_invoice = data_values.get('name')
    frappe.db.sql("""
        UPDATE `tabMy Invoice`
        SET expense_claim = %s, expense_claim_item = %s, status = %s
        WHERE name = %s
    """ , ("", "", "未使用", my_invoice))

    update_expense_item_my_invoice_amount(docname)

def update_expense_item_my_invoice_amount(docname):
    doc = frappe.get_doc('Expense Claim', docname)
    item_wise_amt = frappe.get_all('My Invoice', filters={'expense_claim': doc.name},
        fields=['expense_claim_item', 'sum(deductible_tax_amount) as deductible_tax_amount', 'sum(amount) as my_invoice_amount'],
        group_by ='expense_claim_item'
    )
    item_wise_amt_map = {r.expense_claim_item:r for r in item_wise_amt}
    for row in doc.expenses:
        amt_dict = item_wise_amt_map.get(row.name)        
        if amt_dict:
            amt_dict.pop('expense_claim_item')
            amt_dict.invoice_code = ""
            amt_dict.amount = amt_dict.my_invoice_amount
            amt_dict.sanctioned_amount = amt_dict.amount
            frappe.db.set_value(row.doctype, row.name, amt_dict)
        else:
            frappe.db.set_value(row.doctype, row.name, {'deductible_tax_amount':0, 'my_invoice_amount':0, 'invoice_code':""})            

@frappe.whitelist()
def get_invoice_summary(doc_name) :
    invoice_summary = {
        "火车票" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "汽车票" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "飞机票" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "客运服务" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "乘车服务" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "住宿费" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "通行费" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "通讯费" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "招待费" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "其他" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,
        "小计" : {"未税金额" : 0 , "税额" : 0 , "价税合计" : 0} ,  # 新增小计类型
    }

    invoices = frappe.get_all("My Invoice" , filters={"expense_claim" : doc_name} ,
                              fields=["invoice_type" , "net_amount" , "tax_amount" , "amount"])

    for invoice in invoices :
        invoice_type = invoice.get("invoice_type")
        net_amount = invoice.get("net_amount")
        tax_amount = invoice.get("tax_amount")
        amount = invoice.get("amount")

        if invoice_type in invoice_summary :
            invoice_summary[invoice_type]["未税金额"] += net_amount
            invoice_summary[invoice_type]["税额"] += tax_amount
            invoice_summary[invoice_type]["价税合计"] += amount
            # 更新小计类型
            invoice_summary["小计"]["未税金额"] += net_amount
            invoice_summary["小计"]["税额"] += tax_amount
            invoice_summary["小计"]["价税合计"] += amount
    for invoice_type , values in invoice_summary.items() :
        for key , value in values.items() :
            invoice_summary[invoice_type][key] = round(value , 2)
    for invoice_type, values in invoice_summary.copy().items():
        if values["未税金额"] == 0 and invoice_type != "小计":
            del invoice_summary[invoice_type]
    return invoice_summary
    

@frappe.whitelist()
def get_my_used_invoice(doc_name,expense_claim_item) :
    return frappe.db.sql(
        """select name,invoice_type,invoice_code,net_amount,tax_amount,amount,description,files 
        from `tabMy Invoice`
        where expense_claim=%s and expense_claim_item = %s""",
        (doc_name,expense_claim_item),
        )


@frappe.whitelist()
def get_all_used_invoice(doc_name) :
    return frappe.db.sql(
        """select name,invoice_type,invoice_code,net_amount,tax_amount,amount,description,files 
        from `tabMy Invoice`
        where expense_claim=%s""",
        (doc_name),
        )