import os
import pymupdf  # 直接使用 PyMuPDF 的官方名称
import pandas as pd
from Levenshtein import distance as levenshtein_distance
from call_ali_vl import encode_image, client, recognize_student_info  # 导入需要的函数和客户端
import base64
import json
import argparse  # 新增 argparse 模块
import six
from six.moves import range  # 或者其他需要的模块

def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="根据学生信息拆分PDF文件")
    parser.add_argument('--pdf_path', type=str, help='输入的PDF文件路径')
    parser.add_argument('--output_dir', type=str, default='./output', help='输出目录，默认为./output')
    parser.add_argument('--excel_path', type=str, default=None, help='包含学生信息的Excel文件路径')
    parser.add_argument('--mode', type=str, choices=['ocr', 'excel'], default='ocr',
                       help='切分模式：ocr（默认，使用OCR识别）或excel（按照Excel顺序切分）')
    parser.add_argument('--pages_field', type=str, default='页数',
                       help='Excel中指定每个学生试卷页数的字段名，默认为"页数"')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 调用主处理函数
    split_pdf_by_students(args.pdf_path, args.output_dir, args.excel_path, args.mode, args.pages_field)

def split_pdf_by_students(pdf_path, output_dir='./output', excel_path=None, mode='ocr', pages_field='页数'):
    """
    主函数：根据学生信息拆分PDF
    :param pdf_path: 输入的PDF文件路径
    :param output_dir: 输出目录，默认为./output
    :param excel_path: 包含学生信息的Excel文件路径
    :param mode: 切分模式，'ocr'或'excel'
    :param pages_field: Excel中指定每个学生试卷页数的字段名
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 读取学生信息（如果有）
    student_info = read_student_info(excel_path) if excel_path else None
    
    # 打开PDF文件
    pdf_document = pymupdf.open(pdf_path)
    
    # 处理每一页
    current_student = None
    page_index = 0
    
    if mode == 'excel' and student_info is not None:
        # 按照Excel顺序切分
        for _, row in student_info.iterrows():
            # 获取学生信息
            student_id = str(row['学号'])
            student_name = row['姓名']
            # print(pages_field)
            pages_count = row.get(pages_field, 2)  # 默认为2页
            
            # 创建学生PDF
            current_student = {
                'id': student_id,
                'name': student_name,
                'pages': []
            }
            
            # 添加指定页数的页面
            if pages_count!=pages_count:
                pages_count = 2
            for _ in range(int(pages_count)):
                if page_index < len(pdf_document):
                    current_student['pages'].append(pdf_document[page_index])
                    page_index += 1
                else:
                    break
            
            # 保存学生PDF
            save_student_pdf(current_student, output_dir)
    else:
        # 使用OCR模式（原逻辑）
        for i in range(0, len(pdf_document), 2):
            # 只处理奇数页（学生信息页）
            info_page = pdf_document[i]
            
            # 识别学生信息，传入当前页面索引
            student_id, student_name = extract_student_info(info_page, student_info, i//2)
            
            # 创建或获取当前学生的PDF
            if not current_student or current_student['id'] != student_id:
                if current_student:
                    save_student_pdf(current_student, output_dir)
                current_student = {
                    'id': student_id,
                    'name': student_name,
                    'pages': [info_page]  # 先添加学生信息页
                }
            
            # 添加对应的偶数页（试卷页）
            if i + 1 < len(pdf_document):
                exam_page = pdf_document[i+1]
                current_student['pages'].append(exam_page)
        
        # 保存最后一个学生的PDF
        if current_student:
            save_student_pdf(current_student, output_dir)

def read_student_info(excel_path):
    """
    读取学生信息Excel文件
    :param excel_path: Excel文件路径
    :return: 包含学生信息的DataFrame
    """
    df = pd.read_excel(excel_path)
    return df

def extract_student_info(page, student_info=None, page_index=0):
    """
    从页面中提取学生信息
    :param page: PDF页面对象
    :param student_info: 学生信息DataFrame
    :param page_index: 当前页面索引（用于顺序匹配）
    :return: (学号, 姓名)
    """
    # 获取页面图像
    image_bytes = page.get_pixmap().tobytes()
    
    # 使用封装好的函数识别学生信息
    text = recognize_student_info(image_bytes)
    
    # 解析学号和姓名
    student_id = extract_id_from_text(text)
    student_name = extract_name_from_text(text)
    
    # 如果提供了学生信息，进行校验和修正
    if student_info is not None:
        student_id, student_name = validate_and_correct_info(student_id, student_name, student_info, page_index)
    
    return student_id, student_name

def validate_and_correct_info(student_id, student_name, student_info, page_index):
    """
    校验并修正学生信息
    :param student_id: 识别的学号
    :param student_name: 识别的姓名
    :param student_info: 学生信息DataFrame
    :param page_index: 当前页面索引（用于顺序匹配）
    :return: (修正后的学号, 修正后的姓名)
    """
    # 首先检查完全匹配
    exact_match = student_info[(student_info['学号'] == student_id) & 
                              (student_info['姓名'] == student_name)]
    if not exact_match.empty:
        return student_id, student_name

    # 计算匹配分数
    def calculate_match_score(row, index):
        score = 0
        
        # 学号匹配
        if row['学号'] == student_id:  # 完全匹配
            score += 100
        else:
            # 学号开头匹配（通常包含年级信息）
            if str(row['学号'])[:2] == str(student_id)[:2]:
                score += 30
            # 学号结尾匹配（通常包含个人编号）
            if str(row['学号'])[-2:] == str(student_id)[-2:]:
                score += 30
            # 学号长度匹配
            if len(str(row['学号'])) == len(str(student_id)):
                score += 20

        # 姓名匹配
        if row['姓名'] == student_name:  # 完全匹配
            score += 100
        else:
            # 姓氏匹配
            if row['姓名'][0] == student_name[0]:
                score += 50
            # 名字长度匹配
            if len(row['姓名']) == len(student_name):
                score += 20
            # 编辑距离
            score -= levenshtein_distance(row['姓名'], student_name)

        # 顺序匹配：考虑当前页面与Excel中顺序的接近程度
        position_diff = abs(index - page_index)
        if position_diff < 5:  # 如果位置相差小于5，给予加分
            score += max(0, 50 - position_diff * 10)

        return score

    # 计算每个学生的匹配分数，传入索引信息
    student_info['match_score'] = student_info.reset_index().apply(
        lambda row: calculate_match_score(row, row.name), axis=1)
    
    # 找到最高分的匹配
    best_match = student_info.loc[student_info['match_score'].idxmax()]
    
    # 如果最高分低于阈值，只在姓名前添加警告标识
    if best_match['match_score'] < 100:  # 设置匹配阈值
        print(f"警告：匹配分数较低，可能存在误差：{best_match['学号']}, {best_match['姓名']}")
        return best_match['学号'], f"W.{best_match['姓名']}"
    
    print(f"匹配成功：{best_match['学号']}, {best_match['姓名']}")
    return best_match['学号'], best_match['姓名']

def save_student_pdf(student, output_dir):
    """
    保存学生PDF文件
    :param student: 学生信息字典
    :param output_dir: 输出目录
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    output_pdf = pymupdf.open()
    for page in student['pages']:
        # 创建一个新的页面并复制内容
        new_page = output_pdf.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(page.rect, page.parent, page.number)
    
    filename = f"{student['id']}_{student['name']}.pdf"
    output_path = os.path.join(output_dir, filename)
    output_pdf.save(output_path)
    output_pdf.close()


def extract_id_from_text(text):
    """
    从识别结果中提取学号
    :param text: 识别结果字典
    :return: 学号字符串
    """
    if text and '学号' in text:
        return str(text['学号']).strip()
    return "未知学号"

def extract_name_from_text(text):
    """
    从识别结果中提取姓名
    :param text: 识别结果字典
    :return: 姓名字符串
    """
    if text and '姓名' in text:
        return str(text['姓名']).strip()
    return "未知姓名"

if __name__ == "__main__":
    main()
