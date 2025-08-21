import os
import sys
import json
import uuid
import time
import shutil
import logging
from datetime import datetime
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory, send_file, g
import sqlite3
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
host = os.getenv('host')
port = os.getenv('port')
base_url = f'http://{host}:{port}'

DATA_FOLDER = "./data"

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
DATA_FOLDER = os.path.abspath(DATA_FOLDER)
USER_FOLDER = os.path.abspath(USER_FOLDER)
PIC_FOLDER = os.path.abspath(PIC_FOLDER)
WEBSITES_FOLDER = os.path.abspath(WEBSITES_FOLDER)

gitbook_db_path = os.path.join(DATA_FOLDER, 'gitbook.db')
conn = sqlite3.connect(gitbook_db_path, check_same_thread=False)
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

# 创建file_mapping表（如果不存在）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS file_mapping (
        real_name TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# 首先，添加一个辅助函数来检查指定文件夹中是否已有相同的显示文件名
def check_display_name_duplicate(folder_path, display_name):
    """
    检查指定文件夹中是否已有相同的显示文件名
    :param folder_path: 文件夹路径
    :param display_name: 显示文件名
    :return: 如果存在重复，返回True；否则返回False
    """
    try:
        # 标准化路径
        normalized_folder_path = os.path.abspath(folder_path)
        
        # 查询数据库，检查是否有相同的显示文件名
        cursor.execute(
            "SELECT COUNT(*) FROM file_mapping WHERE display_name = ? AND file_path LIKE ?",
            (display_name, os.path.join(normalized_folder_path, '%'))
        )
        count = cursor.fetchone()[0]
        
        return count > 0
    except Exception as e:
        print(f"检查显示文件名重复时出错: {e}")
        return False

def run_gitbook_command(command, cwd=None):
    """运行 GitBook 命令的辅助函数"""
    env = os.environ.copy()
    env['HOME'] = '/home/appuser'
    env['NODE_PATH'] = '/usr/local/lib/node_modules'
    
    try:
        process = subprocess.run(
            ['gitbook'] + command.split(),
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env,
            timeout=300  # 5分钟超时
        )
        return process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "命令执行超时"
    except Exception as e:
        return -1, "", str(e)


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
                os.makedirs(os.path.dirname(save_path), exist_ok=True,mode=0o777)
                os.chmod(os.path.dirname(save_path), 0o777)
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
                # 复制 book.json 文件
                src_book_json = os.path.join(fixed_showlist_folder, 'book.json')
                dest_book_json = os.path.join(website_folder, 'book.json')
                if os.path.exists(src_book_json):
                    try:
                        shutil.copy2(src_book_json, dest_book_json)
                    except Exception as e:
                        logger.error(f'复制 book.json 文件失败: {str(e)}')
            else:
                logger.warning(f'固定模板文件夹不存在: {fixed_showlist_folder}')

            # 执行 gitbook init 命令
            returncode, stdout, stderr = run_gitbook_command(f'init {website_folder}')

            if returncode != 0:
                # 如果 gitbook init 失败，删除创建的文件夹
                shutil.rmtree(website_folder, ignore_errors=True)
                return jsonify({
                    'error': f'gitbook init 失败: {stderr}'
                }), 500

            logger.info(f"开始执行 gitbook install: {website_folder}")
            returncode, stdout, stderr = run_gitbook_command(f'install {website_folder}')
        
            if returncode != 0:
                logger.error(f"gitbook install 失败: {stderr}")
                return jsonify({
                    'error': f'gitbook install失败: {stderr}'
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
        logger.exception(f"创建网站会话失败: {str(e)}")
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
        
        # 预加载当前目录下所有文件的映射关系
        cursor.execute("SELECT real_name, display_name FROM file_mapping WHERE file_path LIKE ?",
                          (os.path.join(folder_path, '%'),))
        mappings = dict(cursor.fetchall())
        
        for item in items:
            # 过滤掉 _book 文件夹
            if item == '_book' or item == 'node_modules':
                continue

            item_path = os.path.join(folder_path, item)
            # 获取创建时间
            created_time = os.path.getctime(item_path)
            # 格式化为可读时间
            formatted_time = datetime.fromtimestamp(created_time).isoformat()
            
            # 获取显示名称
            display_name = mappings.get(item, item)
            
            if os.path.isdir(item_path):
                # 如果是文件夹，递归读取
                item_info = {
                    'id': time.time() + (hash(display_name) % 1000),
                    'name': display_name,
                    'type': 'folder',
                    'filePath': item_path,  # 添加filePath属性
                    'createdAt': formatted_time,  # 记录创建时间
                    'children': read_folder_structure(item_path)
                }
            elif os.path.isfile(item_path) and item.endswith('.md'):
                # 只处理md文件
                item_info = {
                    'id': time.time() + (hash(display_name) % 1000),
                    'name': display_name,
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
        logger.error("导出电子书失败: 会话ID不能为空")
        return jsonify({'error': '会话ID不能为空'}), 400

    try:
        # 从数据库中获取文件夹路径
        cursor.execute("SELECT folder_path FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()

        if not result:
            logger.error(f"导出电子书失败: 会话不存在 - {session_id}")
            return jsonify({'error': '会话不存在'}), 404

        folder_path = result[0]

        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            logger.error(f"导出电子书失败: 文件夹不存在 - {folder_path}")
            return jsonify({'error': '文件夹不存在'}), 404

        logger.info(f"开始执行 gitbook build: {folder_path}")
        returncode, stdout, stderr = run_gitbook_command(f'build {folder_path}')
        
        if returncode != 0:
            logger.error(f"gitbook build 失败: {stderr}")
            return jsonify({
                'success': False,
                'error': f'gitbook build失败: {stderr}'

            }), 500

        # 移动 _book 文件夹
        source_book_folder = os.path.join(folder_path, '_book')
        if not os.path.exists(source_book_folder):
            logger.error(f"_book文件夹不存在: {source_book_folder}")
            return jsonify({
                'success': False,
                'error': '_book文件夹不存在，请检查gitbook build是否成功'
            }), 500

        target_session_folder = os.path.join(USER_FOLDER, session_id)
        os.makedirs(target_session_folder, exist_ok=True)
        target_book_folder = os.path.join(target_session_folder, '_book')

        if os.path.exists(target_book_folder):
            shutil.rmtree(target_book_folder)

        shutil.move(source_book_folder, target_session_folder)
        logger.info(f"电子书导出成功: {target_book_folder}")

        return jsonify({
            'success': True,
            'message': '导出成功',
            'output': stdout,
            'book_path': target_book_folder
        })
    except Exception as e:
        logger.exception(f"导出电子书时发生异常: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 导出PDF API
@app.route('/api/export-pdf', methods=['POST'])
def export_pdf():
    data = request.json
    session_id = data.get('sessionId')

    if not session_id:
        logger.error("导出PDF失败: 会话ID不能为空")
        return jsonify({'error': '会话ID不能为空'}), 400

    try:
        # 从数据库中获取文件夹路径和名称
        cursor.execute("SELECT folder_path, folder_name FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()

        if not result:
            logger.error(f"导出PDF失败: 会话不存在 - {session_id}")
            return jsonify({'error': '会话不存在'}), 404

        folder_path = result[0]
        folder_name = result[1]

        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            logger.error(f"导出PDF失败: 文件夹不存在 - {folder_path}")
            return jsonify({'error': '文件夹不存在'}), 404

        # 执行 gitbook pdf 命令生成PDF
        pdf_output_path = os.path.join(folder_path, f'{folder_name}.pdf')
        logger.info(f"开始执行 gitbook pdf: {folder_path} -> {pdf_output_path}")
        
        # 使用绝对路径指定输出文件
        returncode, stdout, stderr = run_gitbook_command(f'pdf . {pdf_output_path}', cwd=folder_path)
        
        if returncode != 0:
            logger.error(f"gitbook pdf 失败: {stderr}")
            return jsonify({
                'success': False,
                'error': f'生成PDF失败: {stderr}'
            }), 500

        # 检查PDF文件是否生成成功
        if not os.path.exists(pdf_output_path):
            logger.error(f"PDF文件不存在: {pdf_output_path}")
            return jsonify({
                'success': False,
                'error': 'PDF文件生成失败，请检查日志'
            }), 500

        logger.info(f"PDF导出成功: {pdf_output_path}")
        
        # 返回PDF文件供下载
        return send_file(
            pdf_output_path,
            as_attachment=True,
            download_name=f'{folder_name}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.exception(f"导出PDF时发生异常: {str(e)}")
        return jsonify({'error': str(e)}), 500


# 修改create_file函数，使用更简短的真实文件名
@app.route('/api/create-file', methods=['POST'])
def create_file():
    data = request.json
    target_path = data.get('folderPath')  # 修改参数名以支持文件路径
    display_name = data.get('fileName')
    target_type = data.get('targetType', 'folder')  # 新增参数，默认为folder

    if not target_path or not display_name:
        return jsonify({'error': '目标路径和文件名不能为空'}), 400

    # 确保文件以.md结尾
    if not display_name.endswith('.md'):
        display_name += '.md'

    try:
        # 标准化路径
        normalized_path = os.path.abspath(target_path)
        
        # 如果目标是文件，获取其父目录作为创建路径
        if target_type == 'file' and os.path.isfile(normalized_path):
            normalized_folder_path = os.path.dirname(normalized_path)
        else:
            normalized_folder_path = normalized_path

        # 检查文件夹是否存在
        if not os.path.exists(normalized_folder_path):
            return jsonify({'error': '文件夹不存在'}), 404

        # 检查是否是文件夹
        if not os.path.isdir(normalized_folder_path):
            return jsonify({'error': '提供的路径不是文件夹'}), 400

        # 检查显示文件名是否已存在
        if check_display_name_duplicate(normalized_folder_path, display_name):
            return jsonify({'error': '该名称的文件已存在'}), 400

        # 生成更简短的真实文件名（使用UUID的前8位加上时间戳的最后4位）
        short_uuid = str(uuid.uuid4()).split('-')[0]  # 获取UUID的第一部分（8位）
        timestamp_suffix = str(int(time.time()))[-4:]  # 获取当前时间戳的最后4位
        real_name = f"{short_uuid}_{timestamp_suffix}.md"
        file_path = os.path.join(normalized_folder_path, real_name)

        # 检查生成的简短文件名是否真的不存在（以防极低概率的碰撞）
        while os.path.exists(file_path):
            # 如果发生碰撞，重新生成一个
            short_uuid = str(uuid.uuid4()).split('-')[0]
            timestamp_suffix = str(int(time.time()))[-4:]
            real_name = f"{short_uuid}_{timestamp_suffix}.md"
            file_path = os.path.join(normalized_folder_path, real_name)

        # 创建新文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('')  # 写入空内容

        # 存储映射关系到数据库
        cursor.execute(
            "INSERT INTO file_mapping (real_name, display_name, file_path) VALUES (?, ?, ?)",
            (real_name, display_name, file_path)
        )
        conn.commit()

        # 返回新创建的文件信息（使用显示名称）
        new_file = {
            'id': time.time() + (hash(display_name) % 1000),
            'name': display_name,
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
    target_path = data.get('parentPath')  # 修改参数名以支持文件路径
    folder_name = data.get('folderName')
    target_type = data.get('targetType', 'folder')  # 新增参数，默认为folder

    if not target_path or not folder_name:
        return jsonify({'error': '目标路径和文件夹名不能为空'}), 400

    try:
        # 标准化路径
        normalized_path = os.path.abspath(target_path)
        
        # 如果目标是文件，获取其父目录作为创建路径
        if target_type == 'file' and os.path.isfile(normalized_path):
            normalized_parent_path = os.path.dirname(normalized_path)
        else:
            normalized_parent_path = normalized_path

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
        os.makedirs(new_folder_path, exist_ok=True,mode=0o777)
        os.chmod(new_folder_path, 0o777)

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

        # 显示名称就是原始文件名
        display_name = file.filename
        
        # 检查显示文件名是否已存在
        if check_display_name_duplicate(normalized_folder_path, display_name):
            return jsonify({'error': '该名称的文件已存在'}), 400

        # 生成更简短的真实文件名（使用UUID的前8位加上时间戳的最后4位）
        short_uuid = str(uuid.uuid4()).split('-')[0]  # 获取UUID的第一部分（8位）
        timestamp_suffix = str(int(time.time()))[-4:]  # 获取当前时间戳的最后4位
        real_name = f"{short_uuid}_{timestamp_suffix}.md"
        file_path = os.path.join(normalized_folder_path, real_name)

        # 检查生成的简短文件名是否真的不存在（以防极低概率的碰撞）
        while os.path.exists(file_path):
            # 如果发生碰撞，重新生成一个
            short_uuid = str(uuid.uuid4()).split('-')[0]
            timestamp_suffix = str(int(time.time()))[-4:]
            real_name = f"{short_uuid}_{timestamp_suffix}.md"
            file_path = os.path.join(normalized_folder_path, real_name)

        # 保存文件
        file.save(file_path)

        # 存储映射关系到数据库
        cursor.execute(
            "INSERT INTO file_mapping (real_name, display_name, file_path) VALUES (?, ?, ?)",
            (real_name, display_name, file_path)
        )
        conn.commit()

        # 返回上传的文件信息（使用显示名称）
        uploaded_file = {
            'id': time.time() + (hash(display_name) % 1000),
            'name': display_name,
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
            # 先删除文件夹内所有md文件的映射
            cursor.execute(
                "DELETE FROM file_mapping WHERE file_path LIKE ?",
                (normalized_path + '%',)
            )
            conn.commit()
            
            shutil.rmtree(normalized_path)
            return jsonify({'success': True, 'message': f'文件夹 {os.path.basename(normalized_path)} 已成功删除'})
        else:
            # 删除文件
            # 获取真实文件名
            real_name = os.path.basename(normalized_path)
            # 删除数据库中的映射
            cursor.execute(
                "DELETE FROM file_mapping WHERE real_name = ?",
                (real_name,)
            )
            conn.commit()
            
            os.remove(normalized_path)
            
            # 从数据库获取显示名称用于返回消息
            cursor.execute(
                "SELECT display_name FROM file_mapping WHERE real_name = ?",
                (real_name,)
            )
            result = cursor.fetchone()
            display_name = result[0] if result else real_name
            
            return jsonify({'success': True, 'message': f'文件 {display_name} 已成功删除'})
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
        os.makedirs(session_folder, exist_ok=True,mode=0o777)
        
        # 确保文件夹有正确的权限
        os.chmod(session_folder, 0o777)

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

# 修改文件重命名逻辑，使用显示文件名检查重复
@app.route('/api/rename-item', methods=['POST'])
def api_rename_item():
    data = request.json
    file_path = data.get('filePath')
    new_display_name = data.get('newName')
    is_folder = data.get('isFolder', False)

    # 验证输入参数
    if not file_path:
        return jsonify({'error': '文件路径不能为空'}), 400
    if not new_display_name:
        return jsonify({'error': '新名称不能为空'}), 400
    
    try:
        if is_folder:
            # 文件夹重命名，不需要修改数据库
            success, message = rename_item(file_path, new_display_name, is_folder)
        else:
            # 获取当前真实文件名和父文件夹路径
            normalized_path = os.path.abspath(file_path)
            real_name = os.path.basename(normalized_path)
            parent_path = os.path.dirname(normalized_path)
            
            # 确保文件以.md结尾
            if not new_display_name.endswith('.md'):
                new_display_name += '.md'
            
            # 检查显示文件名是否已存在（这是新增的重要检查）
            if check_display_name_duplicate(parent_path, new_display_name):
                return jsonify({'error': '该名称的文件已存在'}), 400
            
            # 更新数据库中的映射关系
            cursor.execute(
                "UPDATE file_mapping SET display_name = ? WHERE real_name = ?",
                (new_display_name, real_name)
            )
            conn.commit()
            
            success, message = True, f'文件已成功重命名为 "{new_display_name}"'
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    
    # 先处理根目录的README.md，放在最前面
    root_readme = None
    for item in structure:
        if item['type'] == 'file' and item['name'] == 'README.md':
            root_readme = item
            break
    
    # 如果有根目录的README.md，添加到目录最前面
    if root_readme:
        # 计算相对路径（相对于根目录）
        relative_path = os.path.relpath(root_readme['filePath'], folder_path)
         
        # 确定显示名称
        display_name = os.path.splitext(root_readme['name'])[0]
         
        # 添加根目录README.md到目录最前面
        content.append(f'* [{display_name}]({relative_path.replace(os.sep, "/")})')
    
    # 递归遍历文件夹结构，生成目录内容
    def traverse_structure(items, level=0, parent_is_top_level=False):
        # 用于标记当前文件夹中是否已处理过README.md文件
        has_readme = False
        
        # 先收集README.md文件
        readme_file = None
        
        for item in items:
            # 忽略_book和node_modules文件夹
            if item['type'] == 'folder' and item['name'] in ['_book', 'node_modules']:
                continue

            # 跳过根目录的README.md，因为已经单独处理过了
            if level == 0 and item['type'] == 'file' and item['name'] == 'README.md':
                readme_file = item
                has_readme = True
                continue
            elif item['type'] == 'file' and item['name'] == 'README.md':
                # 保存子目录的README.md文件
                readme_file = item
                has_readme = True
            elif item['type'] == 'file' and item['name'].endswith('.md') and item['name'] != 'SUMMARY.md':
                # 计算显示层级
                display_level = 0
                if level <= 1 and parent_is_top_level:
                    # 根目录或根目录下第一层文件夹中的文件
                    display_level = 0
                else:
                    # 其他层级的文件
                    display_level = level
                     
                # 对于非README.md文件，如果当前文件夹有README.md，则显示层级+1
                if level > 0:
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
                display_name = os.path.splitext(item['name'])[0]
                 
                # 添加目录项
                content.append(f'{indent}* [{display_name}]({relative_path.replace(os.sep, "/")})')
            elif item['type'] == 'folder':
                # 处理子文件夹
                folder_name = item['name']
                
                # 计算缩进空格数
                indent = ' ' * (2 * level)
                
                # 查找当前文件夹下是否有README.md
                folder_has_readme = False
                folder_readme_path = ''
                for child in item.get('children', []):
                    if child['type'] == 'file' and child['name'] == 'README.md':
                        folder_has_readme = True
                        folder_readme_path = os.path.relpath(child['filePath'], folder_path)
                        break
                
                # 添加文件夹名称到目录，如果有README.md则链接到README.md
                if folder_has_readme:
                    # 文件夹有README.md，链接指向README.md
                    content.append(f'{indent}* [{folder_name}]({folder_readme_path.replace(os.sep, "/")})')
                else:
                    # 文件夹没有README.md，保持原有方式
                    content.append(f'{indent}* {folder_name}')
                
                # 递归处理子文件夹内容
                if 'children' in item and item['children']:
                    # 标记是否是根目录下的第一层文件夹
                    is_top_level_folder = level == 0
                    traverse_structure(item['children'], level + 1, is_top_level_folder)
        
        # 对于子目录的README.md，已经在文件夹链接中处理，不需要单独添加
    
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