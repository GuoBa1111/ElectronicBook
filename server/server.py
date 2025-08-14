from flask import Flask, request, jsonify, send_from_directory
import os
import json
import uuid
import time
import shutil  # 添加shutil模块用于删除文件夹
from datetime import datetime
import subprocess

app = Flask(__name__)
PORT = 3000
DATA_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')

# 确保data文件夹存在
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER, exist_ok=True)

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
        sessions = []
        # 遍历data文件夹中的所有json文件
        for file in os.listdir(DATA_FOLDER):
            if file.endswith('.json'):
                file_path = os.path.join(DATA_FOLDER, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    # 检查文件夹是否仍然存在
                    if os.path.exists(session_data['folderPath']):
                        sessions.append({
                            'sessionId': session_data['sessionId'],
                            'folderPath': session_data['folderPath'],
                            'createdAt': session_data['createdAt']
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

# 创建文件夹会话API
@app.route('/api/create-folder-session', methods=['POST'])
def create_folder_session():
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

        # 检查是否已存在相同文件夹的会话
        existing_sessions = []
        for file in os.listdir(DATA_FOLDER):
            if file.endswith('.json'):
                file_path = os.path.join(DATA_FOLDER, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    if session_data.get('folderPath') == normalized_path:
                        existing_sessions.append(session_data)

        # 如果存在相同文件夹的会话，返回已有的sessionId
        if existing_sessions:
            return jsonify({'sessionId': existing_sessions[0]['sessionId']})

        # 生成唯一ID
        session_id = str(uuid.uuid4())[:8]

        # 保存会话数据
        session_data = {
            'sessionId': session_id,
            'folderPath': normalized_path,
            'structure': structure,
            'createdAt': datetime.now().isoformat()
        }

        with open(os.path.join(DATA_FOLDER, f'{session_id}.json'), 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

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
        # 查找会话文件
        session_file = os.path.join(DATA_FOLDER, f'{session_id}.json')

        if not os.path.exists(session_file):
            return jsonify({'error': '会话不存在'}), 404

        # 读取会话数据
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)

        # 检查文件夹是否仍然存在
        if not os.path.exists(session_data['folderPath']):
            return jsonify({'error': '关联的文件夹不存在'}), 404

        # 重新读取文件夹结构
        structure = read_folder_structure(session_data['folderPath'])

        return jsonify({
            'structure': structure,
            'folderPath': session_data['folderPath']
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
        for item in items:
            # 过滤掉 _book 文件夹
            if item == '_book':
                continue

            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path):
                # 如果是文件夹，递归读取
                structure.append({
                    'id': time.time() + (hash(item) % 1000),
                    'name': item,
                    'type': 'folder',
                    'filePath': item_path,  # 添加filePath属性
                    'children': read_folder_structure(item_path)
                })
            elif os.path.isfile(item_path) and item.endswith('.md'):
                # 只处理md文件
                structure.append({
                    'id': time.time() + (hash(item) % 1000),
                    'name': item,
                    'type': 'file',
                    'filePath': item_path
                })
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
        # 查找会话文件
        session_file = os.path.join(DATA_FOLDER, f'{session_id}.json')

        if not os.path.exists(session_file):
            return jsonify({'error': '会话不存在'}), 404

        # 读取会话数据
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)

        # 获取文件夹路径
        folder_path = session_data['folderPath']

        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            return jsonify({'error': '文件夹不存在'}), 404

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

        return jsonify({
            'success': True,
            'message': '导出成功',
            'output': process.stdout
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 修改通配符路由，返回dist文件夹中的index.html
# 添加通配符路由，用于处理前端路由
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # 如果请求的是API路径，则继续404
    if path.startswith('api/'):
        return jsonify({'error': '路径不存在'}), 404
    # 其他所有请求都返回dist文件夹中的index.html
    try:
        return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'dist'), 'index.html')
    except Exception as e:
        return jsonify({'error': f'无法提供静态文件: {str(e)}'}), 500

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

if __name__ == '__main__':
    print(f'服务器运行在 http://localhost:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=True)