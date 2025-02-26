import os
import uuid
import shutil
import zipfile
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, send_file, session
from werkzeug.utils import secure_filename
from pdf_process import split_pdf_by_students

app = Flask(__name__)
app.secret_key = "pdf_splitter_secret_key"  # 设置session密钥

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS_PDF = {'pdf'}
ALLOWED_EXTENSIONS_EXCEL = {'xlsx', 'xls'}

# 确保上传和输出目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # 检查是否有文件被上传
    if 'pdf_file' not in request.files or 'excel_file' not in request.files:
        return redirect(request.url)
    
    pdf_file = request.files['pdf_file']
    excel_file = request.files['excel_file']
    
    # 检查文件名是否为空
    if pdf_file.filename == '' or excel_file.filename == '':
        return redirect(request.url)
    
    # 检查文件类型
    if not (allowed_file(pdf_file.filename, ALLOWED_EXTENSIONS_PDF) and 
            allowed_file(excel_file.filename, ALLOWED_EXTENSIONS_EXCEL)):
        return render_template('index.html', error="请上传有效的PDF和Excel文件")
    
    # 创建一个唯一的任务ID
    task_id = str(uuid.uuid4())
    task_upload_folder = os.path.join(UPLOAD_FOLDER, task_id)
    task_output_folder = os.path.join(OUTPUT_FOLDER, task_id)
    
    os.makedirs(task_upload_folder, exist_ok=True)
    os.makedirs(task_output_folder, exist_ok=True)
    
    # 保存上传的文件
    pdf_path = os.path.join(task_upload_folder, secure_filename(pdf_file.filename))
    excel_path = os.path.join(task_upload_folder, secure_filename(excel_file.filename))
    
    pdf_file.save(pdf_path)
    excel_file.save(excel_path)
    
    # 调用PDF拆分函数（使用excel模式）
    split_pdf_by_students(pdf_path, task_output_folder, excel_path, 'excel', '页数')
    
    # 创建ZIP文件
    zip_filename = f"split_pdfs_{task_id}.zip"
    zip_path = os.path.join(task_output_folder, zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(task_output_folder):
            for file in files:
                if file.endswith('.pdf'):  # 只打包PDF文件
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, task_output_folder)
                    zipf.write(file_path, arcname)
    
    # 将任务ID存入session
    session['task_id'] = task_id
    session['zip_path'] = zip_path
    
    return redirect(url_for('result', task_id=task_id))

@app.route('/result/<task_id>')
def result(task_id):
    zip_path = session.get('zip_path')
    if not zip_path or not os.path.exists(zip_path):
        return render_template('index.html', error="处理失败，请重试")
    
    return render_template('result.html', task_id=task_id)

@app.route('/download/<task_id>')
def download(task_id):
    zip_path = session.get('zip_path')
    if not zip_path or not os.path.exists(zip_path):
        return redirect(url_for('index'))
    
    # 创建响应并设置cookie，标记此任务需要清理
    response = send_file(zip_path, as_attachment=True, download_name=f"拆分的PDF文件.zip")
    
    # 下载后直接执行清理
    task_upload_folder = os.path.join(UPLOAD_FOLDER, task_id)
    task_output_folder = os.path.join(OUTPUT_FOLDER, task_id)
    
    # 设置cookie，在另一个请求中进行清理
    response.set_cookie('cleanup_task', task_id, max_age=300)  # 5分钟内有效
    
    return response

# 添加一个清理路由，当用户下载后会自动触发
@app.route('/cleanup')
def cleanup():
    task_id = request.cookies.get('cleanup_task')
    if task_id:
        task_upload_folder = os.path.join(UPLOAD_FOLDER, task_id)
        task_output_folder = os.path.join(OUTPUT_FOLDER, task_id)
        
        try:
            if os.path.exists(task_upload_folder):
                shutil.rmtree(task_upload_folder)
                print(f"已清理上传文件夹: {task_upload_folder}")
            if os.path.exists(task_output_folder):
                shutil.rmtree(task_output_folder)
                print(f"已清理输出文件夹: {task_output_folder}")
        except Exception as e:
            print(f"清理文件时出错: {e}")
            
    return '', 204  # 返回无内容

# 文件清理后台任务
def file_cleanup_task():
    while True:
        try:
            # 每隔10分钟检查一次
            time.sleep(600)
            
            # 获取当前时间
            current_time = time.time()
            
            # 检查上传目录
            for task_id in os.listdir(UPLOAD_FOLDER):
                task_path = os.path.join(UPLOAD_FOLDER, task_id)
                if os.path.isdir(task_path):
                    # 获取文件夹的修改时间
                    modified_time = os.path.getmtime(task_path)
                    # 如果文件夹超过30分钟未修改，则删除
                    if (current_time - modified_time) > 1800:  # 30分钟
                        shutil.rmtree(task_path)
                        print(f"清理过期上传文件夹: {task_path}")
            
            # 检查输出目录
            for task_id in os.listdir(OUTPUT_FOLDER):
                task_path = os.path.join(OUTPUT_FOLDER, task_id)
                if os.path.isdir(task_path):
                    # 获取文件夹的修改时间
                    modified_time = os.path.getmtime(task_path)
                    # 如果文件夹超过30分钟未修改，则删除
                    if (current_time - modified_time) > 1800:  # 30分钟
                        shutil.rmtree(task_path)
                        print(f"清理过期输出文件夹: {task_path}")
        
        except Exception as e:
            print(f"清理任务出错: {e}")

# 启动清理线程
cleanup_thread = threading.Thread(target=file_cleanup_task, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 