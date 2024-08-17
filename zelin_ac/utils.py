import frappe
import os
import io
import json
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


def get_ofd_xml(file_url):
    file_doc = frappe.get_doc('File', {'file_url': file_url})
    path =f"{frappe.utils.get_bench_path()}/sites{file_doc.get_full_path()[1:]}"
    with OFDParser(path) as parser:        
        return parser.get_first_xbrl_data_dict()