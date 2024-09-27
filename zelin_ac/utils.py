import frappe
import os
import io
import json
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict


class OFDParser:
    def __init__(self, ofd_file_path):
        self.ofd_file_path = ofd_file_path
        self.extracted_path = self.extract_ofd(ofd_file_path)
        #Doc_0 linux里区分大小写，doc_0不行。
        self.attachments_file_path = os.path.join(self.extracted_path, 'Doc_0', 'Attachs', 'Attachments.xml')

    def extract_ofd(self, ofd_file_path):
        """
        Extract the OFD file to a temporary directory.
        """
        extract_dir = os.path.join(os.path.dirname(ofd_file_path), 'extracted_ofd')
        result = os.makedirs(extract_dir, exist_ok=True)        
        with zipfile.ZipFile(ofd_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # print(f"OFD file extracted to: {extract_dir}")
        # print(f"Contents of the extracted directory: {os.listdir(extract_dir)}")
        
        return extract_dir

    def get_xbrl_filenames(self): # 得到xbrl文件名数组
        """
        Parse the attachments.xml file to get a list of XBRL filenames.
        """
        if not os.path.exists(self.attachments_file_path):
            print(f"Attachments.xml not found at {self.attachments_file_path}")
            return []

        # 解析 XML 文件
        tree = ET.parse(self.attachments_file_path)
        root = tree.getroot()

        # 定义命名空间
        namespaces = {'ofd': 'http://www.ofdspec.org/2016'}  # ABC, CCB

        xbrl_filenames = []
        for attachment in root.findall('ofd:Attachment', namespaces):
            file_loc_element = attachment.find('ofd:FileLoc', namespaces)
            if file_loc_element is not None:
                filename = file_loc_element.text
                if filename:
                    xbrl_filenames.append(filename)
                else:
                    print("No filename found in FileLoc element.")
            else:
                print("FileLoc element not found in attachment element.")

        if not xbrl_filenames:
            print("No XBRL filenames found in attachments.xml.")

        return xbrl_filenames                

    def read_first_xbrl_file(self): # 返回第一个xbrl文件的内容
        """
        Read the content of the first XBRL file found in the directory.
        """
        xbrl_filenames = self.get_xbrl_filenames()
        for filename in xbrl_filenames:
            file_path = os.path.join(self.extracted_path, 'Doc_0', 'Attachs', filename)
            if os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if content:
                        return content
                    else:
                        print(f"XBRL file {filename} is empty.")
            else:
                print(f"XBRL file {filename} not found at {file_path}.")
        return None


    """
    ET.iterparse 期望的是文件路径或文件对象，而传递的是一个字符串（XML 文本内容）。
    解决方法是将字符串内容解析为一个文件对象，然后再进行解析。
    可以使用 io.StringIO 将字符串转换为文件对象。
    """

    def get_all_namespaces(self, xml_content):
        """
        Get all namespaces from an element tree.
        """
        namespaces = dict([
            node for _, node in ET.iterparse(
                io.StringIO(xml_content), events=['start-ns']
            )
        ])
        return namespaces


        """
        # Define necessary namespaces (adjust as needed)
        namespaces = {
            'xbrl': 'http://www.xbrl.org/2003/instance', # ABC, CCB
            'bker': 'http://xbrl.mof.gov.cn/taxonomy/2023-05-15/bker'  # CCB
            # 'bker': 'http://xbrl.mof.gov.cn/taxonomy/2021-11-30/bker'   # ABC
        }
        虽然可以直接使用 root.findall('.//bker:*')，但前提是需要处理 XML 中可能存在的多个命名空间问题。
        由于 ElementTree 模块不支持直接忽略命名空间，只能通过提供命名空间映射来查找元素。
        """
        
    def parse_xbrl_content(self, xbrl_content): # 实际解析xbrl内容，返回字典名值对    
        """
        Parse the content of an XBRL file and return it as a dictionary.
        """
        tree = ET.ElementTree(ET.fromstring(xbrl_content))
        root = tree.getroot()

        namespaces = self.get_all_namespaces(xbrl_content)
        
        # 每个标签可能会有多个值。使用 defaultdict(list) 是为了在这些情况出现时能够正确地收集所有值。
        # 空， 一个值， 多个值， 都能适配，如： [],  [3], [2, 4]
        result = defaultdict(list)  

        # Define the namespace prefix to look for
        namespace_prefix = 'bker'

        for prefix, uri in namespaces.items():
            if prefix == namespace_prefix:
                for elem in root.findall('.//{}:*'.format(prefix), namespaces):
                    # Remove the namespace and extract the element name
                    tag_name = elem.tag.split('}', 1)[1]
                    result[tag_name].append(elem.text)

        return result

    def get_first_xbrl_data_dict(self):  # 返回第一个xbrl文件解析后的字典名值对
        """
        Get the parsed data of the first XBRL file as a dictionary.
        """
        xbrl_content = self.read_first_xbrl_file()
        if xbrl_content:
            return self.parse_xbrl_content(xbrl_content)
        else:
            print("No XBRL content found.")
        return None

    def cleanup(self):
        """
        Clean up the extracted directory.
        """
        if os.path.exists(self.extracted_path):
            shutil.rmtree(self.extracted_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def get_xml_string(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content

    def get_einvoice_xml(self, file_path_content, file_path_customtag):
        xml_string = self.get_xml_string(file_path_content)
        tree = ET.ElementTree(ET.fromstring(xml_string))
        root = tree.getroot()
        namespaces = self.get_all_namespaces(xml_string)
        results = []
        id_mapping = self.get_tag_id_mapping(file_path_customtag)
        for text_object in root.findall('.//ofd:TextObject', namespaces):
            text_id = text_object.get('ID')
            text_id = id_mapping.get(text_id, text_id)
            if text_id:
                node = text_object.find('ofd:TextCode', namespaces)
                text_content = node.text
                results.append([text_id, text_content])
        return {r[0]:r[1] for r in results}

    def get_tag_id_mapping(self, file_path_customtag):
        xml_string = self.get_xml_string(file_path_customtag)
        tree = ET.ElementTree(ET.fromstring(xml_string))
        root = tree.getroot()
        namespaces = self.get_all_namespaces(xml_string)
        mapping = {}
        for elem in root.iter():  
            # Check if the element has a child named 'ofd:ObjectRef'  
            if elem.find('.//ofd:ObjectRef', namespaces) is not None:  
                # Get the text of the 'ofd:ObjectRef' child  
                tag_name = elem.tag.split('}')[-1]  
                elements = elem.findall('.//ofd:ObjectRef', namespaces)
                for sub_elem in elements:
                    obj_ref_text = sub_elem.text
                    # The tag name of the current element is the desired value # Note: elem.tag returns the fully qualified name including the namespace  
                    # So we need to split it and take the last part # Store the mapping  
                    mapping[obj_ref_text] = tag_name
        return mapping        

    def get_xml(self):
        file_path_content = os.path.join(self.extracted_path, 'Doc_0', 'Pages', 'Page_0', 'Content.xml')
        file_path_customtag = os.path.join(self.extracted_path, 'Doc_0', 'Tags', 'CustomTag.xml')
        if os.path.isfile(file_path_content) and os.path.isfile(file_path_customtag):
            xml_content = self.get_einvoice_xml(file_path_content, file_path_customtag)
        else:
            xml_content = self.get_first_xbrl_data_dict()
        return xml_content

def get_ofd_xml(file_url):
    file_doc = frappe.get_doc('File', {'file_url': file_url})
    path =f"{frappe.utils.get_bench_path()}/sites{file_doc.get_full_path()[1:]}"
    
    with OFDParser(path) as parser:        
        return parser.get_xml()

  
def move_file_to_sub_directory(directory_parts, file_doc):  
    """  
    将文件file_doc由源目录移动到由directory_parts指定的多层目录中。       
    :param directory_parts: 目录部分的列表，例如['expense_claim', 'ec0001']  
    :param file_doc: 源文件单据  
    """

    try:
        file_path = file_doc.get_full_path()
        folder = file_doc.folder
        #globals().update(locals())
        directory_parts = [sanitize_filename(frappe.scrub(d)) for d in directory_parts]  
        dir_path_no_slash = os.path.dirname(file_path)  
        base_dir = dir_path_no_slash + '/' if not dir_path_no_slash.endswith('/') else dir_path_no_slash 
        target_dir = os.path.join(base_dir, *directory_parts)  
        target_file_path = os.path.join(target_dir, os.path.basename(file_path))  

        if not os.path.exists(target_dir):  
            os.makedirs(target_dir)

        for part in directory_parts:
            previous_folder = folder
            folder = f"{folder}/{part}"
            if not frappe.db.exists('File', folder):
                frappe.get_doc(
                    {
                        "doctype": "File",
                        "folder": previous_folder,
                        "is_folder": 1,
                        "is_attachments_folder": 1,
                         #autoname: parent/file_name, 
                        "file_name": part, 
                    }
                ).insert(ignore_if_duplicate=True)        
          
        shutil.move(file_path, target_file_path)
        #去掉./site_name前缀
        file_url = target_file_path.replace(frappe.utils.get_site_base_path(),'')
        frappe.db.set_value('File', file_doc.name, 
            {
                'folder': folder,
                'file_url': file_url
            }
        )
        return target_file_path  
    except Exception as e:
        traceback = frappe.get_traceback(with_context=True)
        frappe.log_error("File move to subfolder error", traceback)            
        print(f"移动文件时发生错误: {e}")

def sanitize_filename(filename):  
    special_chars_regex = r'[/\0<>:\*?"\|\\]'  
    sanitized_filename = re.sub(special_chars_regex, '', filename)  
    return sanitized_filename 

def extract_amount(s):      
    # 使用正则表达式匹配字符串中的数字部分，包括小数点和小数部分 \d+ 表示一个或多个数字  
    # (?:\.\d+)? 表示非捕获组，匹配小数点后跟一个或多个数字，但整个组不包含在最终的匹配结果中，且该部分是可选的  
    # ^[^0-9]*(?P<amount>\d+(?:,\d+)*(?:\.\d+)?) 匹配不以数字开头的任意字符（包括空字符串），然后捕获数字部分  
    # 注意：这里假设货币金额中的千分位分隔符是逗号，如果不是，请相应修改正则表达式  
    match = re.match(r'^[^0-9]*(?P<amount>\d+(?:,\d+)*(?:\.\d+)?)', s)           
    return frappe.utils.flt(match.group('amount').replace(',', '') if match  else "")        