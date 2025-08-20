import os
import sys
import json
import uuid
import time
import shutil  # 添加shutil模块用于删除文件夹
from datetime import datetime
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory
import sqlite3
from dotenv import load_dotenv
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

app = Flask(__name__)
host = os.getenv('host')
port = os.getenv('port')
base_url = f'http://{host}:{port}'

DATA_FOLDER = "C:\\Users\\DEH\\Desktop\\E-book\\backend\\data"

USER_FOLDER = os.path.join(DATA_FOLDER, 'userdb')
PIC_FOLDER = os.path.join(DATA_FOLDER, 'pic')
WEBSITES_FOLDER = os.path.join(DATA_FOLDER, 'websites')


# 确保data和pic文件夹存在
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER, exist_ok=True)
if not os.path.exists(PIC_FOLDER):
    os.makedirs(PIC_FOLDER, exist_ok=True)
if not os.path.exists(USER_FOLDER):
    os.makedirs(USER_FOLDER, exist_ok=True)
if not os.path.exists(WEBSITES_FOLDER):
    os.makedirs(WEBSITES_FOLDER, exist_ok=True)

# 转为绝对路径
USER_FOLDER = os.path.abspath(USER_FOLDER)
PIC_FOLDER = os.path.abspath(PIC_FOLDER)
WEBSITES_FOLDER = os.path.abspath(WEBSITES_FOLDER)


sessions_db_path = os.path.join(DATA_FOLDER, 'sessions.db')
conn = sqlite3.connect(sessions_db_path, check_same_thread=False)
cursor = conn.cursor()

# 创建sessions表（如果不存在）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        folder_name TEXT NOT NULL,
        folder_path TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# 新增：上传图片文件API (用于处理编辑器内粘贴或拖入的图片)
@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    # 检查是否有文件上传
    if 'file[]' not in request.files:
        return jsonify({
            'msg': '没有文件上传',
            'code': 1,
            'data': {'errFiles': [], 'succMap': {}}
        }), 400

    files = request.files.getlist('file[]')
    succ_map = {}
    err_files = []

    for file in files:
        if file.filename == '':
            err_files.append('')
            continue

        try:
            # 生成唯一文件名
            ext = os.path.splitext(file.filename)[1].lower()
            print(f'文件扩展名: {ext}')  # 调试信息
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                err_files.append(file.filename)
                print(f'文件格式不支持: {file.filename}, 扩展名: {ext}')  # 调试信息
                continue

            unique_filename = f'{str(uuid.uuid4())[:8]}{ext}'  # 修复UUID使用问题
            save_path = os.path.join(PIC_FOLDER, unique_filename)
            print(f'保存路径: {save_path}')  # 调试信息

            # 检查目录是否存在且可写
            if not os.path.exists(os.path.dirname(save_path)):
                print(f'目录不存在: {os.path.dirname(save_path)}')
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                print(f'已创建目录: {os.path.dirname(save_path)}')

            # 保存文件
            file.save(save_path)
            print(f'文件保存成功: {save_path}')  # 调试信息

            # 生成访问URL，使用与前端相同的IP地址
            image_url = f'{base_url}/api/get-image/{unique_filename}'
            succ_map[file.filename] = image_url
        except Exception as e:
            print(f'上传图片失败: {str(e)}')
            err_files.append(file.filename)

    return jsonify({
        'msg': '',
        'code': 0,
        'data': {
            'errFiles': err_files,
            'succMap': succ_map
        }
    })

# 新增：从URL上传图片API (用于处理站外图片地址)
@app.route('/api/upload-image-from-url', methods=['POST'])
def upload_image_from_url():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({
            'msg': '图片URL不能为空',
            'code': 1,
            'data': {}
        }), 400

    try:
        # 下载图片
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # 获取文件扩展名
        ext = os.path.splitext(url.split('?')[0])[1].lower()
        if not ext or ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            ext = '.png'  # 默认使用png格式

        # 生成唯一文件名
        unique_filename = f'{str(uuid.uuid4())[:8]}{ext}'  # 修复UUID使用问题
        save_path = os.path.join(PIC_FOLDER, unique_filename)

        # 保存图片
        with open(save_path, 'wb') as f:
            f.write(response.content)

        # 生成访问URL
        image_url = f'{base_url}/api/get-image/{unique_filename}'

        return jsonify({
            'msg': '',
            'code': 0,
            'data': {
                'originalURL': url,
                'url': image_url
            }
        })
    except Exception as e:
        print(f'从URL上传图片失败: {str(e)}')
        return jsonify({
            'msg': str(e),
            'code': 1,
            'data': {}
        }), 500

# 新增：获取图片API
@app.route('/api/get-image/<filename>')
def get_image(filename):
    try:
        return send_from_directory(PIC_FOLDER, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# 允许跨域
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response
    
# 新增：获取所有文件夹会话API
@app.route('/api/get-all-sessions', methods=['GET'])
def get_all_sessions():
    try:
        # 从数据库中查询所有会话记录
        cursor.execute("SELECT session_id, folder_name, folder_path, created_at FROM sessions")
        sessions_data = cursor.fetchall()
        
        sessions = []
        for session in sessions_data:
            # 将会话数据转换为前端需要的格式
            sessions.append({
                'sessionId': session[0],  # session_id
                'folderName': session[1],  # folder_name
                'folderPath': session[2],  # folder_path
                'createdAt': session[3]  # created_at
            })
        
        return jsonify({'sessions': sessions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 静态文件服务
# 静态文件服务 - 修改为指向dist文件夹
@app.route('/public/<path:filename>')
def serve_public(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'public'), filename)

# 新增：服务dist文件夹中的静态资源
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'dist', 'assets'), filename)

# 新增：创建网站会话 API
@app.route('/api/create-website-session', methods=['POST'])
def create_website_session():
    data = request.json
    folder_name = data.get('folderName')

    if not folder_name:
        return jsonify({'error': '文件夹名称不能为空'}), 400

    try:
        # 构建网站文件夹路径
        website_folder = os.path.join(WEBSITES_FOLDER, folder_name)
        # 定义固定模板文件夹路径
        fixed_showlist_folder = os.path.join(DATA_FOLDER, 'fixed_ShowlistFold')

        # 检查文件夹是否存在
        if not os.path.exists(website_folder):
            # 创建文件夹
            os.makedirs(website_folder, exist_ok=True)

            # 检查固定模板文件夹是否存在
            if os.path.exists(fixed_showlist_folder):
                # 复制 node_modules 文件夹
                src_node_modules = os.path.join(fixed_showlist_folder, 'node_modules')
                dest_node_modules = os.path.join(website_folder, 'node_modules')
                if os.path.exists(src_node_modules):
                    try:
                        # 使用 shutil.copytree 复制文件夹
                        shutil.copytree(src_node_modules, dest_node_modules)
                    except Exception as e:
                        print(f'复制 node_modules 文件夹失败: {str(e)}')

                # 复制 book.json 文件
                src_book_json = os.path.join(fixed_showlist_folder, 'book.json')
                dest_book_json = os.path.join(website_folder, 'book.json')
                if os.path.exists(src_book_json):
                    try:
                        # 使用 shutil.copy2 复制文件
                        shutil.copy2(src_book_json, dest_book_json)
                    except Exception as e:
                        print(f'复制 book.json 文件失败: {str(e)}')
            else:
                print(f'固定模板文件夹不存在: {fixed_showlist_folder}')

            # 执行 gitbook init 命令
            process = subprocess.run(
                ['gitbook', 'init', website_folder],
                capture_output=True,
                text=True,
                shell=True
            )

            if process.returncode != 0:
                # 如果 gitbook init 失败，删除创建的文件夹
                shutil.rmtree(website_folder, ignore_errors=True)
                return jsonify({
                    'error': f'gitbook init 失败: {process.stderr}'
                }), 500

        # 检查是否已存在相同文件夹的会话
        cursor.execute("SELECT session_id FROM sessions WHERE folder_path = ?", (website_folder,))
        existing_session = cursor.fetchone()

        # 如果存在相同文件夹的会话，返回已有的 sessionId
        if existing_session:
            return jsonify({'sessionId': existing_session[0]})

        # 生成唯一 ID
        session_id = str(uuid.uuid4())[:8]

        # 创建会话文件夹
        session_folder = os.path.join(USER_FOLDER, session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        cursor.execute(
            "INSERT INTO sessions (session_id, folder_name, folder_path) VALUES (?, ?, ?)",
            (session_id, folder_name, website_folder)
        )
        conn.commit()

        return jsonify({'sessionId': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 获取文件夹会话API
@app.route('/api/get-folder-session', methods=['GET'])
def get_folder_session():
    session_id = request.args.get('id')

    if not session_id:
        return jsonify({'error': '会话ID不能为空'}), 400

    try:
        # 查找会话文件夹
        cursor.execute("SELECT folder_path FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'error': '会话不存在'}), 404

        folder_path = result[0]

        if not os.path.exists(folder_path):
            return jsonify({'error': '文件夹不存在'}), 404

         # 读取文件夹结构
        structure = read_folder_structure(folder_path)

        return jsonify({
            'structure': structure,
            'folderPath': folder_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 获取文件夹结构的API
@app.route('/api/read-folder', methods=['POST'])
def read_folder():
    data = request.json
    folder_path = data.get('folderPath')

    if not folder_path:
        return jsonify({'error': '文件夹路径不能为空'}), 400

    try:
        # 标准化路径
        normalized_path = os.path.abspath(folder_path)

        # 检查路径是否存在
        if not os.path.exists(normalized_path):
            return jsonify({'error': '文件夹不存在'}), 404

        # 检查是否是文件夹
        if not os.path.isdir(normalized_path):
            return jsonify({'error': '提供的路径不是文件夹'}), 400

        # 读取文件夹结构
        structure = read_folder_structure(normalized_path)
        return jsonify(structure)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 递归读取文件夹结构
def read_folder_structure(folder_path):
    structure = []
    try:
        items = os.listdir(folder_path)
        item_list = []
        
        for item in items:
            # 过滤掉 _book 文件夹
            if item == '_book' or item == 'node_modules':
                continue

            item_path = os.path.join(folder_path, item)
            # 获取创建时间
            created_time = os.path.getctime(item_path)
            # 格式化为可读时间
            formatted_time = datetime.fromtimestamp(created_time).isoformat()
            
            if os.path.isdir(item_path):
                # 如果是文件夹，递归读取
                item_info = {
                    'id': time.time() + (hash(item) % 1000),
                    'name': item,
                    'type': 'folder',
                    'filePath': item_path,  # 添加filePath属性
                    'createdAt': formatted_time,  # 记录创建时间
                    'children': read_folder_structure(item_path)
                }
            elif os.path.isfile(item_path) and item.endswith('.md'):
                # 只处理md文件
                item_info = {
                    'id': time.time() + (hash(item) % 1000),
                    'name': item,
                    'type': 'file',
                    'filePath': item_path,
                    'createdAt': formatted_time  # 记录创建时间
                }
            else:
                # 跳过不符合条件的项目
                continue
                
            item_list.append((item_info, created_time))
        
        # 按创建时间排序
        sorted_items = sorted(item_list, key=lambda x: x[1])
        # 提取排序后的项目信息
        structure = [item[0] for item in sorted_items]
        
    except Exception as e:
        print(f"Error reading folder structure: {e}")
    return structure

# 获取文件内容的API
@app.route('/api/file-content', methods=['GET'])
def get_file_content():
    file_path = request.args.get('filePath')

    if not file_path:
        return jsonify({'error': '文件路径不能为空'}), 400

    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 保存文件内容的API
@app.route('/api/save-file', methods=['POST'])
def save_file():
    data = request.json
    file_path = data.get('filePath')
    content = data.get('content')

    if not file_path:
        return jsonify({'error': '文件路径不能为空'}), 400

    if content is None:
        return jsonify({'error': '文件内容不能为空'}), 400

    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        # 写入文件内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': '文件保存成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 启动服务器
# 导出电子书API
@app.route('/api/export-book', methods=['POST'])
def export_book():
    data = request.json
    session_id = data.get('sessionId')

    if not session_id:
        return jsonify({'error': '会话ID不能为空'}), 400

    try:
        # 从数据库中获取文件夹路径
        cursor.execute("SELECT folder_path FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'error': '会话不存在'}), 404

        folder_path = result[0]

        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            return jsonify({'error': '文件夹不存在'}), 404

        process = subprocess.run(
            ['gitbook', 'install', folder_path],
            capture_output=True,
            text=True,
            shell=True  # 在Windows上可能需要
        )

        if process.returncode != 0:
            return jsonify({
                'success': False,
                'error': f'gitbook install失败: {process.stderr}'
            }), 500

        # 执行gitbook build命令
        # 注意：这里假设gitbook-cli已安装并且在系统PATH中
        process = subprocess.run(
            ['gitbook', 'build', folder_path],
            capture_output=True,
            text=True,
            shell=True  # 在Windows上可能需要
        )

        if process.returncode != 0:
            return jsonify({
                'success': False,
                'error': f'gitbook build失败: {process.stderr}'
            }), 500

        # 新增：移动_book文件夹到data目录下对应的会话文件夹
        # 构建源_book文件夹路径
        source_book_folder = os.path.join(folder_path, '_book')
        if not os.path.exists(source_book_folder):
            return jsonify({
                'success': False,
                'error': '_book文件夹不存在，请检查gitbook build是否成功'
            }), 500

        # 构建目标文件夹路径 (data/{session_id})
        target_session_folder = os.path.join(USER_FOLDER, session_id)
        os.makedirs(target_session_folder, exist_ok=True)

        # 构建目标_book文件夹路径
        target_book_folder = os.path.join(target_session_folder, '_book')

        # 如果目标_book文件夹已存在，则先删除
        if os.path.exists(target_book_folder):
            shutil.rmtree(target_book_folder)

        # 移动_book文件夹
        shutil.move(source_book_folder, target_session_folder)

        return jsonify({
            'success': True,
            'message': '导出成功',
            'output': process.stdout,
            'book_path': target_book_folder
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 创建新文件API
@app.route('/api/create-file', methods=['POST'])
def create_file():
    data = request.json
    folder_path = data.get('folderPath')
    file_name = data.get('fileName')

    if not folder_path or not file_name:
        return jsonify({'error': '文件夹路径和文件名不能为空'}), 400

    # 确保文件以.md结尾
    if not file_name.endswith('.md'):
        file_name += '.md'

    try:
        # 标准化路径
        normalized_folder_path = os.path.abspath(folder_path)

        # 检查文件夹是否存在
        if not os.path.exists(normalized_folder_path):
            return jsonify({'error': '文件夹不存在'}), 404

        # 检查是否是文件夹
        if not os.path.isdir(normalized_folder_path):
            return jsonify({'error': '提供的路径不是文件夹'}), 400

        # 构建文件路径
        file_path = os.path.join(normalized_folder_path, file_name)

        # 检查文件是否已存在
        if os.path.exists(file_path):
            return jsonify({'error': '文件已存在'}), 400

        # 创建新文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('')  # 写入空内容

        # 返回新创建的文件信息
        new_file = {
            'id': time.time() + (hash(file_name) % 1000),
            'name': file_name,
            'type': 'file',
            'filePath': file_path
        }

        return jsonify(new_file)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 创建新文件夹API
@app.route('/api/create-folder', methods=['POST'])
def create_new_folder():
    data = request.json
    parent_path = data.get('parentPath')
    folder_name = data.get('folderName')

    if not parent_path or not folder_name:
        return jsonify({'error': '父文件夹路径和文件夹名不能为空'}), 400

    try:
        # 标准化路径
        normalized_parent_path = os.path.abspath(parent_path)

        # 检查父文件夹是否存在
        if not os.path.exists(normalized_parent_path):
            return jsonify({'error': '父文件夹不存在'}), 404

        # 检查是否是文件夹
        if not os.path.isdir(normalized_parent_path):
            return jsonify({'error': '提供的父路径不是文件夹'}), 400

        # 构建新文件夹路径
        new_folder_path = os.path.join(normalized_parent_path, folder_name)

        # 检查文件夹是否已存在
        if os.path.exists(new_folder_path):
            return jsonify({'error': '文件夹已存在'}), 400

        # 创建新文件夹
        os.makedirs(new_folder_path, exist_ok=True)
        
        # 自动创建README.md文件
        readme_path = os.path.join(new_folder_path, "README.md")
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write('')

        # 返回新创建的文件夹信息
        new_folder = {
            'id': time.time() + (hash(folder_name) % 1000),
            'name': folder_name,
            'type': 'folder',
            'children': []
        }

        return jsonify(new_folder)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 上传文件API
@app.route('/api/upload-file', methods=['POST'])
def upload_file():
    # 检查是否有文件上传
    if 'file' not in request.files:
        return jsonify({'error': '没有文件上传'}), 400

    file = request.files['file']
    folder_path = request.form.get('folderPath')

    if not folder_path:
        return jsonify({'error': '文件夹路径不能为空'}), 400

    # 如果用户没有选择文件，浏览器会提交一个空文件，这里需要检查
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    # 确保文件以.md结尾
    if not file.filename.endswith('.md'):
        return jsonify({'error': '只能上传.md文件'}), 400

    try:
        # 标准化路径
        normalized_folder_path = os.path.abspath(folder_path)

        # 检查文件夹是否存在
        if not os.path.exists(normalized_folder_path):
            return jsonify({'error': '文件夹不存在'}), 404

        # 检查是否是文件夹
        if not os.path.isdir(normalized_folder_path):
            return jsonify({'error': '提供的路径不是文件夹'}), 400

        # 构建文件路径
        file_path = os.path.join(normalized_folder_path, file.filename)

        # 保存文件
        file.save(file_path)

        # 返回上传的文件信息
        uploaded_file = {
            'id': time.time() + (hash(file.filename) % 1000),
            'name': file.filename,
            'type': 'file',
            'filePath': file_path
        }

        return jsonify(uploaded_file)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#  添加删除文件/文件夹的API
@app.route('/api/delete-item', methods=['POST'])
def delete_item():
    data = request.json
    file_path = data.get('filePath')
    is_folder = data.get('isFolder', False)

    if not file_path:
        return jsonify({'error': '文件路径不能为空'}), 400

    try:
        # 标准化路径
        normalized_path = os.path.abspath(file_path)

        # 检查路径是否存在
        if not os.path.exists(normalized_path):
            return jsonify({'error': '文件或文件夹不存在'}), 404

        if is_folder:
            # 删除文件夹及其内容
            shutil.rmtree(normalized_path)
            return jsonify({'success': True, 'message': f'文件夹 {os.path.basename(normalized_path)} 已成功删除'})
        else:
            # 删除文件
            os.remove(normalized_path)
            return jsonify({'success': True, 'message': f'文件 {os.path.basename(normalized_path)} 已成功删除'})
    except PermissionError:
        return jsonify({'error': '权限不足，无法删除文件或文件夹'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增：编辑会话API (修改文件夹名称)
@app.route('/api/edit-session', methods=['POST'])
def edit_session():
    data = request.json
    session_id = data.get('sessionId')
    new_name = data.get('newName')

    if not session_id or not new_name:
        return jsonify({'error': '会话ID和新名称不能为空'}), 400

    try:
         # 从数据库中获取原文件夹路径
        cursor.execute("SELECT folder_path FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'error': '会话不存在'}), 404

        old_folder_path = result[0]
        parent_path = os.path.dirname(old_folder_path)

        # 构建新的文件夹路径
        new_folder_path = os.path.join(parent_path, new_name)

        # 检查新名称的文件夹是否已存在
        if os.path.exists(new_folder_path):
            return jsonify({'error': '该名称的文件夹已存在'}), 400

        # 重命名文件夹
        os.rename(old_folder_path, new_folder_path)

       # 更新数据库中的文件夹路径和名称
        cursor.execute(
            "UPDATE sessions SET folder_name = ?, folder_path = ? WHERE session_id = ?",
            (new_name, new_folder_path, session_id)
        )
        conn.commit()

        # 重新读取文件夹结构
        # session_data['structure'] = read_folder_structure(new_folder_path)

        return jsonify({'success': True, 'message': '会话更新成功', 'newFolderPath': new_folder_path})
    except PermissionError:
        return jsonify({'error': '权限不足，无法重命名文件夹'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增：删除会话API (只删除会话记录，不删除实际文件)
@app.route('/api/delete-session', methods=['POST'])
def delete_session():
    data = request.json
    session_id = data.get('sessionId')

    if not session_id:
        return jsonify({'error': '会话ID不能为空'}), 400

    try:
        # 从数据库中删除会话记录
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()

        # 删除会话文件夹
        session_folder = os.path.join(USER_FOLDER, session_id)
        if os.path.exists(session_folder) and os.path.isdir(session_folder):
            shutil.rmtree(session_folder)

        return jsonify({'success': True, 'message': '会话已成功删除'})
    except PermissionError:
        return jsonify({'error': '权限不足，无法删除会话文件夹'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 添加重命名文件/文件夹的API
def rename_item(file_path, new_name, is_folder=False):
    """
    重命名文件或文件夹
    :param file_path: 要重命名的文件或文件夹路径
    :param new_name: 新名称
    :param is_folder: 是否是文件夹
    :return: (success, message)
    """
    try:
        # 标准化路径
        normalized_path = os.path.abspath(file_path)

        # 检查路径是否存在
        if not os.path.exists(normalized_path):
            return False, '文件或文件夹不存在'

        # 检查是否为正确的类型
        if is_folder and not os.path.isdir(normalized_path):
            return False, '提供的路径不是文件夹'
        if not is_folder and not os.path.isfile(normalized_path):
            return False, '提供的路径不是文件'

        # 获取父文件夹路径
        parent_path = os.path.dirname(normalized_path)

        # 构建新的路径
        new_path = os.path.join(parent_path, new_name)

        # 检查新名称是否已存在
        if os.path.exists(new_path):
            return False, '该名称的文件或文件夹已存在'

        # 执行重命名操作
        os.rename(normalized_path, new_path)

        return True, f'{"文件夹" if is_folder else "文件"} "{os.path.basename(normalized_path)}" 已成功重命名为 "{new_name}"'  
    except PermissionError:
        return False, '权限不足，无法重命名'
    except Exception as e:
        return False, str(e)

@app.route('/api/rename-item', methods=['POST'])
def api_rename_item():
    data = request.json
    file_path = data.get('filePath')
    new_name = data.get('newName')
    is_folder = data.get('isFolder', False)

    # 验证输入参数
    if not file_path:
        return jsonify({'error': '文件路径不能为空'}), 400
    if not new_name:
        return jsonify({'error': '新名称不能为空'}), 400
    
    # 调用重命名函数
    success, message = rename_item(file_path, new_name, is_folder)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

# 添加在文件末尾，if __name__ == '__main__': 之前

# 新增：导出目录API
def generate_summary_md(folder_path):
    """
    生成SUMMARY.md文件内容
    :param folder_path: 文件夹路径
    :return: SUMMARY.md文件内容
    """
    content = ['# Summary']
    
    # 获取文件夹结构
    structure = read_folder_structure(folder_path)
    
    # 递归遍历文件夹结构，生成目录内容
    def traverse_structure(items, level=0, parent_is_top_level=False):
        # 用于标记当前文件夹中是否已处理过README.md文件
        has_readme = False
        
        for item in items:
            # 忽略_book和node_modules文件夹
            if item['type'] == 'folder' and item['name'] in ['_book', 'node_modules']:
                continue

            if item['type'] == 'file' and item['name'].endswith('.md') and item['name'] != 'SUMMARY.md':
                # 检查是否是README.md文件
                is_readme = item['name'] == 'README.md'
                
                # 如果是README.md，标记当前文件夹有README
                if is_readme:
                    has_readme = True
                    
                # 计算显示层级
                display_level = 0
                if level <= 1 and parent_is_top_level:
                    # 根目录或根目录下第一层文件夹中的文件
                    display_level = 0
                else:
                    # 其他层级的文件
                    display_level = level
                    
                # 对于非README.md文件，如果当前文件夹有README.md，则显示层级+1
                if not is_readme and level > 0:
                    # 检查当前文件夹是否有README.md
                    for sibling in items:
                        if sibling['type'] == 'file' and sibling['name'] == 'README.md':
                            display_level += 1
                            break
                
                # 计算缩进空格数
                indent = ' ' * (2 * display_level)
                # 计算相对路径（相对于根目录）
                relative_path = os.path.relpath(item['filePath'], folder_path)
                
                # 确定显示名称
                if item['name'] == 'README.md':
                    # 获取文件所在目录的路径
                    file_dir = os.path.dirname(item['filePath'])
                    # 如果文件不在根目录下（即目录路径不等于根目录路径）
                    if file_dir != folder_path:
                        # 使用所在文件夹的名称作为显示名称
                        display_name = os.path.basename(file_dir)
                    else:
                        # 根目录下的README.md，使用文件名（不含扩展名）作为显示名称
                        display_name = os.path.splitext(item['name'])[0]
                else:
                    # 其他md文件，使用文件名（不含扩展名）作为显示名称
                    display_name = os.path.splitext(item['name'])[0]
                
                # 添加目录项
                content.append(f'{indent}* [{display_name}]({relative_path.replace(os.sep, "/")})')
            elif item['type'] == 'folder':
                # 递归处理子文件夹
                if 'children' in item and item['children']:
                    # 标记是否是根目录下的第一层文件夹
                    is_top_level_folder = level == 0
                    traverse_structure(item['children'], level + 1, is_top_level_folder)
    
    # 开始遍历
    traverse_structure(structure)
    
    # 用换行符连接所有内容
    return '\n'.join(content)
    
@app.route('/api/export-summary', methods=['POST'])
def export_summary():
    data = request.json
    session_id = data.get('sessionId')
    
    if not session_id:
        return jsonify({'error': '会话ID不能为空'}), 400
    
    try:
        # 从数据库中获取文件夹路径
        cursor.execute("SELECT folder_path FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': '会话不存在'}), 404
        
        folder_path = result[0]
        
        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            return jsonify({'error': '文件夹不存在'}), 404
        
        # 生成SUMMARY.md文件内容
        summary_content = generate_summary_md(folder_path)
        
        # 构建SUMMARY.md文件路径
        summary_path = os.path.join(folder_path, 'SUMMARY.md')
        
        # 写入文件
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        return jsonify({
            'success': True,
            'message': '目录已成功导出到 SUMMARY.md',
            'summaryPath': summary_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f'服务器运行在 http://{base_url}')
    app.run(host='0.0.0.0', port=port, debug=True)