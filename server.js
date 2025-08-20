// 转换为ES模块导入语法
import express from 'express';
import fs from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { exec } from 'child_process';
import request from 'request';
import cors from 'cors';
import multer from 'multer';

// 从配置文件导入数据
import { SERVER_CONFIG } from '../config.js';

const app = express();
const host = SERVER_CONFIG.host;
const PORT = SERVER_CONFIG.port;
const base_url = `http://${host}:${PORT}`;

const DATA_FOLDER = SERVER_CONFIG.dataPath;
const USER_FOLDER = path.join(DATA_FOLDER, 'userdb');
const PIC_FOLDER = path.join(DATA_FOLDER, 'pic');
const WEBSITES_FOLDER = path.join(DATA_FOLDER, 'websites');

// 确保data和pic文件夹存在
function ensureDirectoryExistence(dir) {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
}

ensureDirectoryExistence(DATA_FOLDER);
ensureDirectoryExistence(PIC_FOLDER);
ensureDirectoryExistence(USER_FOLDER);
ensureDirectoryExistence(WEBSITES_FOLDER);

// 自定义删除文件夹函数
function deleteFolderRecursive(folderPath) {
    if (fs.existsSync(folderPath)) {
        fs.readdirSync(folderPath).forEach((file) => {
            const curPath = path.join(folderPath, file);
            if (fs.lstatSync(curPath).isDirectory()) {
                deleteFolderRecursive(curPath);
            } else {
                fs.unlinkSync(curPath);
            }
        });
        fs.rmdirSync(folderPath);
    }
}

const storage = multer.memoryStorage();
const upload = multer({ storage: storage });

// 配置多文件上传
const uploadMultiple = multer({ storage: storage }).array('file[]');

// 中间件
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

app.post('/api/upload-image', (req, res) => {
    uploadMultiple(req, res, (err) => {
        if (err) {
            console.error('上传图片失败:', err);
            return res.status(500).json({
                msg: '文件上传失败',
                code: 1,
                data: { errFiles: [], succMap: {} }
            });
        }

        // 检查是否有文件上传
        if (!req.files || req.files.length === 0) {
            return res.status(400).json({
                msg: '没有文件上传',
                code: 1,
                data: { errFiles: [], succMap: {} }
            });
        }

        const files = req.files;
        const succMap = {};
        const errFiles = [];

        files.forEach(file => {
            try {
                // 获取文件扩展名
                const ext = path.extname(file.originalname).toLowerCase();
                console.log(`文件扩展名: ${ext}`);
                
                if (!['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'].includes(ext)) {
                    errFiles.push(file.originalname);
                    console.log(`文件格式不支持: ${file.originalname}, 扩展名: ${ext}`);
                    return;
                }

                // 生成唯一文件名
                const uniqueFilename = `${uuidv4().slice(0, 8)}${ext}`;
                const savePath = path.join(PIC_FOLDER, uniqueFilename);
                console.log(`保存路径: ${savePath}`);

                // 检查目录是否存在且可写
                if (!fs.existsSync(path.dirname(savePath))) {
                    console.log(`目录不存在: ${path.dirname(savePath)}`);
                    fs.mkdirSync(path.dirname(savePath), { recursive: true });
                    console.log(`已创建目录: ${path.dirname(savePath)}`);
                }

                // 保存文件
                fs.writeFileSync(savePath, file.buffer);
                console.log(`文件保存成功: ${savePath}`);

                // 生成访问URL
                const imageUrl = `${base_url}/api/get-image/${uniqueFilename}`;
                succMap[file.originalname] = imageUrl;
            } catch (e) {
                console.error(`上传图片失败: ${file.originalname}, 错误: ${e.message}`);
                errFiles.push(file.originalname);
            }
        });

        return res.json({
            msg: '',
            code: 0,
            data: {
                errFiles: errFiles,
                succMap: succMap
            }
        });
    });
});

// 新增：从URL上传图片API (用于处理站外图片地址)
app.post('/api/upload-image-from-url', (req, res) => {
    try {
        const { url } = req.body;

        if (!url) {
            return res.status(400).json({
                msg: '图片URL不能为空',
                code: 1,
                data: {}
            });
        }

        // 下载图片
        request.get({ url, timeout: 10000, encoding: null }, (error, response, body) => {
            if (error || response.statusCode !== 200) {
                console.error('从URL上传图片失败:', error || `HTTP ${response.statusCode}`);
                return res.status(500).json({
                    msg: error ? error.message : `HTTP ${response.statusCode}`,
                    code: 1,
                    data: {}
                });
            }

            try {
                // 获取文件扩展名
                let ext = path.extname(url.split('?')[0]).toLowerCase();
                if (!ext || !['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'].includes(ext)) {
                    ext = '.png'; // 默认使用png格式
                }

                // 生成唯一文件名
                const uniqueFilename = `${uuidv4().slice(0, 8)}${ext}`;
                const savePath = path.join(PIC_FOLDER, uniqueFilename);

                // 检查目录是否存在
                if (!fs.existsSync(path.dirname(savePath))) {
                    fs.mkdirSync(path.dirname(savePath), { recursive: true });
                }

                // 保存图片
                fs.writeFileSync(savePath, body);
                console.log(`图片保存成功: ${savePath}`);

                // 生成访问URL
                const imageUrl = `${base_url}/api/get-image/${uniqueFilename}`;

                res.json({
                    msg: '',
                    code: 0,
                    data: {
                        originalURL: url,
                        url: imageUrl
                    }
                });
            } catch (e) {
                console.error('保存图片失败:', e);
                res.status(500).json({
                    msg: e.message,
                    code: 1,
                    data: {}
                });
            }
        });
    } catch (error) {
        console.error('从URL上传图片失败:', error);
        res.status(500).json({ error: error.message });
    }
});

// 新增：获取图片API
app.get('/api/get-image/:filename', (req, res) => {
    try {
        const { filename } = req.params;
        res.sendFile(path.join(PIC_FOLDER, filename));
    } catch (error) {
        res.status(404).json({ error: '图片不存在' });
    }
});

// 新增：获取所有文件夹会话API
app.get('/api/get-all-sessions', (req, res) => {
    try {
        const sessions = [];
        
        // 遍历data文件夹中的所有子文件夹
        if (fs.existsSync(USER_FOLDER)) {
            const folders = fs.readdirSync(USER_FOLDER);
            folders.forEach(folder => {
                const folderPath = path.join(USER_FOLDER, folder);
                if (fs.statSync(folderPath).isDirectory()) {
                    const sessionFile = path.join(folderPath, 'session.json');
                    if (fs.existsSync(sessionFile)) {
                        const sessionData = JSON.parse(fs.readFileSync(sessionFile, 'utf-8'));
                        // 检查文件夹是否仍然存在
                        if (fs.existsSync(sessionData.folderPath)) {
                            sessions.push({
                                sessionId: sessionData.sessionId,
                                folderPath: sessionData.folderPath,
                                createdAt: sessionData.createdAt
                            });
                        }
                    }
                }
            });
        }
        
        res.json({ sessions });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 静态文件服务
app.get('/public/:filename', (req, res) => {
    try {
        const { filename } = req.params;
        const filePath = path.join(__dirname, '..', 'public', filename);
        res.sendFile(filePath);
    } catch (error) {
        res.status(404).json({ error: '文件不存在' });
    }
});

// 新增：服务dist文件夹中的静态资源
app.get('/assets/:filename', (req, res) => {
    try {
        const { filename } = req.params;
        const filePath = path.join(__dirname, '..', 'dist', 'assets', filename);
        res.sendFile(filePath);
    } catch (error) {
        res.status(404).json({ error: '文件不存在' });
    }
});

// 新增：创建网站会话 API
app.post('/api/create-website-session', (req, res) => {
    try {
        const { folderName } = req.body;

        if (!folderName) {
            return res.status(400).json({ error: '文件夹名称不能为空' });
        }

        // 构建网站文件夹路径
        const websiteFolder = path.join(WEBSITES_FOLDER, folderName);
        // 定义固定模板文件夹路径
        const fixedShowlistFolder = path.join(DATA_FOLDER, 'fixed_ShowlistFold');

        // 检查文件夹是否存在
        if (!fs.existsSync(websiteFolder)) {
            // 创建文件夹
            fs.mkdirSync(websiteFolder, { recursive: true });

            // 检查固定模板文件夹是否存在
            if (fs.existsSync(fixedShowlistFolder)) {
                // 复制 node_modules 文件夹
                const srcNodeModules = path.join(fixedShowlistFolder, 'node_modules');
                const destNodeModules = path.join(websiteFolder, 'node_modules');
                if (fs.existsSync(srcNodeModules)) {
                    try {
                        // 复制文件夹（简化版，实际可能需要更复杂的递归复制）
                        // 在实际项目中，可以使用第三方库如 fs-extra 的 copySync
                        copyDirectory(srcNodeModules, destNodeModules);
                    } catch (e) {
                        console.error('复制 node_modules 文件夹失败:', e.message);
                    }
                }

                // 复制 book.json 文件
                const srcBookJson = path.join(fixedShowlistFolder, 'book.json');
                const destBookJson = path.join(websiteFolder, 'book.json');
                if (fs.existsSync(srcBookJson)) {
                    try {
                        fs.copyFileSync(srcBookJson, destBookJson);
                    } catch (e) {
                        console.error('复制 book.json 文件失败:', e.message);
                    }
                }
            } else {
                console.error(`固定模板文件夹不存在: ${fixedShowlistFolder}`);
            }

            // 执行 gitbook init 命令
            exec(`gitbook init "${websiteFolder}"`, (error, stdout, stderr) => {
                if (error) {
                    // 如果 gitbook init 失败，删除创建的文件夹
                    try {
                        deleteFolderRecursive(websiteFolder);
                    } catch (e) {
                        console.error('删除文件夹失败:', e.message);
                    }
                    return res.status(500).json({
                        error: `gitbook init 失败: ${stderr}`
                    });
                }

                // 继续处理
                processAfterGitbookInit();
            });
        } else {
            processAfterGitbookInit();
        }

        function processAfterGitbookInit() {
            try {
                // 检查是否已存在相同文件夹的会话
                let existingSession = null;
                if (fs.existsSync(USER_FOLDER)) {
                    const files = fs.readdirSync(USER_FOLDER);
                    for (const file of files) {
                        const folderPath = path.join(USER_FOLDER, file);
                        if (fs.statSync(folderPath).isDirectory()) {
                            const sessionFile = path.join(folderPath, 'session.json');
                            if (fs.existsSync(sessionFile)) {
                                const sessionData = JSON.parse(fs.readFileSync(sessionFile, 'utf-8'));
                                if (sessionData.folderPath === websiteFolder) {
                                    existingSession = sessionData;
                                    break;
                                }
                            }
                        }
                    }
                }

                // 如果存在相同文件夹的会话，返回已有的 sessionId
                if (existingSession) {
                    return res.json({ sessionId: existingSession.sessionId });
                }

                // 生成唯一 ID
                const sessionId = uuidv4().slice(0, 8);

                // 创建会话文件夹
                const sessionFolder = path.join(USER_FOLDER, sessionId);
                fs.mkdirSync(sessionFolder, { recursive: true });

                // 读取文件夹结构
                const structure = readFolderStructure(websiteFolder);

                // 保存会话数据
                const sessionData = {
                    sessionId,
                    folderPath: websiteFolder,
                    structure,
                    createdAt: new Date().toISOString()
                };

                fs.writeFileSync(
                    path.join(sessionFolder, 'session.json'),
                    JSON.stringify(sessionData, null, 2),
                    'utf-8'
                );

                res.json({ sessionId });
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 获取文件夹会话API
app.get('/api/get-folder-session', (req, res) => {
    try {
        const { id: sessionId } = req.query;

        if (!sessionId) {
            return res.status(400).json({ error: '会话ID不能为空' });
        }

        // 查找会话文件夹
        const sessionFolder = path.join(USER_FOLDER, sessionId);

        if (!fs.existsSync(sessionFolder) || !fs.statSync(sessionFolder).isDirectory()) {
            return res.status(404).json({ error: '会话不存在' });
        }

        // 查找会话文件
        const sessionFile = path.join(sessionFolder, 'session.json');

        if (!fs.existsSync(sessionFile)) {
            return res.status(404).json({ error: '会话不存在' });
        }

        // 读取会话数据
        const sessionData = JSON.parse(fs.readFileSync(sessionFile, 'utf-8'));

        // 检查文件夹是否仍然存在
        if (!fs.existsSync(sessionData.folderPath)) {
            return res.status(404).json({ error: '关联的文件夹不存在' });
        }

        // 重新读取文件夹结构
        const structure = readFolderStructure(sessionData.folderPath);

        res.json({
            structure,
            folderPath: sessionData.folderPath
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 获取文件夹结构的API
app.post('/api/read-folder', (req, res) => {
    try {
        const { folderPath } = req.body;

        if (!folderPath) {
            return res.status(400).json({ error: '文件夹路径不能为空' });
        }

        // 标准化路径
        const normalizedPath = path.resolve(folderPath);

        // 检查路径是否存在
        if (!fs.existsSync(normalizedPath)) {
            return res.status(404).json({ error: '文件夹不存在' });
        }

        // 检查是否是文件夹
        if (!fs.statSync(normalizedPath).isDirectory()) {
            return res.status(400).json({ error: '提供的路径不是文件夹' });
        }

        // 读取文件夹结构
        const structure = readFolderStructure(normalizedPath);
        res.json(structure);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 递归读取文件夹结构
function readFolderStructure(folderPath) {
    const structure = [];
    try {
        const items = fs.readdirSync(folderPath);
        const itemList = [];
        
        for (const item of items) {
            // 过滤掉 _book 文件夹
            if (item === '_book' || item === 'node_modules') {
                continue;
            }

            const itemPath = path.join(folderPath, item);
            // 获取创建时间
            const stats = fs.statSync(itemPath);
            const createdTime = stats.birthtime.getTime();
            // 格式化为可读时间
            const formattedTime = stats.birthtime.toISOString();
            
            if (stats.isDirectory()) {
                // 如果是文件夹，递归读取
                const itemInfo = {
                    id: Date.now() + (hash(item) % 1000),
                    name: item,
                    type: 'folder',
                    filePath: itemPath,  // 添加filePath属性
                    createdAt: formattedTime,  // 记录创建时间
                    children: readFolderStructure(itemPath)
                };
                itemList.push([itemInfo, createdTime]);
            } else if (stats.isFile() && item.endsWith('.md')) {
                // 只处理md文件
                const itemInfo = {
                    id: Date.now() + (hash(item) % 1000),
                    name: item,
                    type: 'file',
                    filePath: itemPath,
                    createdAt: formattedTime  // 记录创建时间
                };
                itemList.push([itemInfo, createdTime]);
            }
            // 跳过不符合条件的项目
        }
        
        // 按创建时间排序
        itemList.sort((a, b) => a[1] - b[1]);
        // 提取排序后的项目信息
        for (const item of itemList) {
            structure.push(item[0]);
        }
        
    } catch (error) {
        console.error(`Error reading folder structure: ${error.message}`);
    }
    return structure;
}

// 获取文件内容的API
app.get('/api/file-content', (req, res) => {
    try {
        const { filePath } = req.query;

        if (!filePath) {
            return res.status(400).json({ error: '文件路径不能为空' });
        }

        // 检查文件是否存在
        if (!fs.existsSync(filePath)) {
            return res.status(404).json({ error: '文件不存在' });
        }

        // 读取文件内容
        const content = fs.readFileSync(filePath, 'utf-8');
        res.json({ content });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 保存文件内容的API
app.post('/api/save-file', (req, res) => {
    try {
        const { filePath, content } = req.body;

        if (!filePath) {
            return res.status(400).json({ error: '文件路径不能为空' });
        }

        if (content === undefined) {
            return res.status(400).json({ error: '文件内容不能为空' });
        }

        // 检查文件是否存在
        if (!fs.existsSync(filePath)) {
            return res.status(404).json({ error: '文件不存在' });
        }

        // 写入文件内容
        fs.writeFileSync(filePath, content, 'utf-8');
        res.json({ success: true, message: '文件保存成功' });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 导出电子书API
app.post('/api/export-book', (req, res) => {
    try {
        const { sessionId } = req.body;

        if (!sessionId) {
            return res.status(400).json({ error: '会话ID不能为空' });
        }

        // 查找会话文件
        const SESSION_FOLDER = path.join(USER_FOLDER, sessionId);
        const sessionFile = path.join(SESSION_FOLDER, 'session.json');

        if (!fs.existsSync(sessionFile)) {
            return res.status(404).json({ error: '会话不存在' });
        }

        // 读取会话数据
        const sessionData = JSON.parse(fs.readFileSync(sessionFile, 'utf-8'));

        // 获取文件夹路径
        const folderPath = sessionData.folderPath;

        // 检查文件夹是否存在
        if (!fs.existsSync(folderPath)) {
            return res.status(404).json({ error: '文件夹不存在' });
        }

        // 执行gitbook build命令
        exec(`gitbook build "${folderPath}"`, (error, stdout, stderr) => {
            if (error) {
                return res.status(500).json({
                    success: false,
                    error: `gitbook build失败: ${stderr}`
                });
            }

            try {
                // 新增：移动_book文件夹到data目录下对应的会话文件夹
                // 构建源_book文件夹路径
                const sourceBookFolder = path.join(folderPath, '_book');
                if (!fs.existsSync(sourceBookFolder)) {
                    return res.status(500).json({
                        success: false,
                        error: '_book文件夹不存在，请检查gitbook build是否成功'
                    });
                }

                // 构建目标文件夹路径 (data/{session_id})
                const targetSessionFolder = path.join(USER_FOLDER, sessionId);
                fs.mkdirSync(targetSessionFolder, { recursive: true });

                // 构建目标_book文件夹路径
                const targetBookFolder = path.join(targetSessionFolder, '_book');

                // 如果目标_book文件夹已存在，则先删除
                if (fs.existsSync(targetBookFolder)) {
                    deleteFolderRecursive(targetBookFolder);
                }

                // 移动_book文件夹
                // 在Node.js中，fs.renameSync对于跨设备移动可能会失败，这里使用复制后删除的方式
                copyDirectory(sourceBookFolder, targetBookFolder);
                deleteFolderRecursive(sourceBookFolder);

                res.json({
                    success: true,
                    message: '导出成功',
                    output: stdout,
                    book_path: targetBookFolder
                });
            } catch (e) {
                res.status(500).json({ error: e.message });
            }
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 创建新文件API
app.post('/api/create-file', (req, res) => {
    try {
        const { folderPath, fileName } = req.body;

        if (!folderPath || !fileName) {
            return res.status(400).json({ error: '文件夹路径和文件名不能为空' });
        }

        // 确保文件以.md结尾
        let normalizedFileName = fileName;
        if (!fileName.endsWith('.md')) {
            normalizedFileName += '.md';
        }

        // 标准化路径
        const normalizedFolderPath = path.resolve(folderPath);

        // 检查文件夹是否存在
        if (!fs.existsSync(normalizedFolderPath)) {
            return res.status(404).json({ error: '文件夹不存在' });
        }

        // 检查是否是文件夹
        if (!fs.statSync(normalizedFolderPath).isDirectory()) {
            return res.status(400).json({ error: '提供的路径不是文件夹' });
        }

        // 构建文件路径
        const filePath = path.join(normalizedFolderPath, normalizedFileName);

        // 检查文件是否已存在
        if (fs.existsSync(filePath)) {
            return res.status(400).json({ error: '文件已存在' });
        }

        // 创建新文件
        fs.writeFileSync(filePath, '', 'utf-8');

        // 返回新创建的文件信息
        const newFile = {
            id: Date.now() + (hash(normalizedFileName) % 1000),
            name: normalizedFileName,
            type: 'file',
            filePath
        };

        res.json(newFile);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 创建新文件夹API
app.post('/api/create-folder', (req, res) => {
    try {
        const { parentPath, folderName } = req.body;

        if (!parentPath || !folderName) {
            return res.status(400).json({ error: '父文件夹路径和文件夹名不能为空' });
        }

        // 标准化路径
        const normalizedParentPath = path.resolve(parentPath);

        // 检查父文件夹是否存在
        if (!fs.existsSync(normalizedParentPath)) {
            return res.status(404).json({ error: '父文件夹不存在' });
        }

        // 检查是否是文件夹
        if (!fs.statSync(normalizedParentPath).isDirectory()) {
            return res.status(400).json({ error: '提供的父路径不是文件夹' });
        }

        // 构建新文件夹路径
        const newFolderPath = path.join(normalizedParentPath, folderName);

        // 检查文件夹是否已存在
        if (fs.existsSync(newFolderPath)) {
            return res.status(400).json({ error: '文件夹已存在' });
        }

        // 创建新文件夹
        fs.mkdirSync(newFolderPath, { recursive: true });

        // 返回新创建的文件夹信息
        const newFolder = {
            id: Date.now() + (hash(folderName) % 1000),
            name: folderName,
            type: 'folder',
            children: []
        };

        res.json(newFolder);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 上传文件API
// 2. 配置multer中间件
// 配置内存存储，用于处理上传的文件


app.post('/api/upload-file', (req, res) => {
    try {
        // 检查是否有文件上传
        if (!req.files || req.files.length === 0) {
            return res.status(400).json({
                msg: '没有文件上传',
                code: 1,
                data: { errFiles: [], succMap: {} }
            });
        }

        const files = req.files;
        const succMap = {};
        const errFiles = [];

        files.forEach(file => {
            try {
                // 获取文件扩展名
                const ext = path.extname(file.originalname).toLowerCase();
                console.log(`文件扩展名: ${ext}`);
                
                if (!['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'].includes(ext)) {
                    errFiles.push(file.originalname);
                    console.log(`文件格式不支持: ${file.originalname}, 扩展名: ${ext}`);
                    return;
                }

                // 生成唯一文件名
                const uniqueFilename = `${uuidv4().slice(0, 8)}${ext}`;
                const savePath = path.join(PIC_FOLDER, uniqueFilename);
                console.log(`保存路径: ${savePath}`);

                // 检查目录是否存在且可写
                if (!fs.existsSync(path.dirname(savePath))) {
                    console.log(`目录不存在: ${path.dirname(savePath)}`);
                    fs.mkdirSync(path.dirname(savePath), { recursive: true });
                    console.log(`已创建目录: ${path.dirname(savePath)}`);
                }

                // 保存文件
                fs.writeFileSync(savePath, file.buffer);
                console.log(`文件保存成功: ${savePath}`);

                // 生成访问URL
                const imageUrl = `${base_url}/api/get-image/${uniqueFilename}`;
                succMap[file.originalname] = imageUrl;
            } catch (e) {
                console.error(`上传图片失败: ${file.originalname}, 错误: ${e.message}`);
                errFiles.push(file.originalname);
            }
        });

        return res.json({
            msg: '',
            code: 0,
            data: {
                errFiles: errFiles,
                succMap: succMap
            }
        });
    } catch (error) {
        console.error('上传图片失败:', error);
        res.status(500).json({ error: error.message });
    }
});

// 4. 完整实现上传文件API
app.post('/api/upload-file', upload.single('file'), (req, res) => {
    try {
        // 检查是否有文件上传
        if (!req.file) {
            return res.status(400).json({ error: '没有文件上传' });
        }

        const file = req.file;
        const folderPath = req.body.folderPath;

        if (!folderPath) {
            return res.status(400).json({ error: '文件夹路径不能为空' });
        }

        // 确保文件以.md结尾
        if (!file.originalname.endsWith('.md')) {
            return res.status(400).json({ error: '只能上传.md文件' });
        }

        // 标准化路径
        const normalizedFolderPath = path.resolve(folderPath);

        // 检查文件夹是否存在
        if (!fs.existsSync(normalizedFolderPath)) {
            return res.status(404).json({ error: '文件夹不存在' });
        }

        // 检查是否是文件夹
        if (!fs.statSync(normalizedFolderPath).isDirectory()) {
            return res.status(400).json({ error: '提供的路径不是文件夹' });
        }

        // 构建文件路径
        const file_path = path.join(normalizedFolderPath, file.originalname);

        // 保存文件
        fs.writeFileSync(file_path, file.buffer);

        // 返回上传的文件信息
        const uploaded_file = {
            id: Date.now() + (hash(file.originalname) % 1000),
            name: file.originalname,
            type: 'file',
            filePath: file_path
        };

        res.json(uploaded_file);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 添加删除文件/文件夹的API
app.post('/api/delete-item', (req, res) => {
    try {
        const { filePath, isFolder = false } = req.body;

        if (!filePath) {
            return res.status(400).json({ error: '文件路径不能为空' });
        }

        // 标准化路径
        const normalizedPath = path.resolve(filePath);

        // 检查路径是否存在
        if (!fs.existsSync(normalizedPath)) {
            return res.status(404).json({ error: '文件或文件夹不存在' });
        }

        if (isFolder) {
            // 删除文件夹及其内容
            try {
                deleteFolderRecursive(normalizedPath);
                res.json({
                    success: true,
                    message: `文件夹 ${path.basename(normalizedPath)} 已成功删除`
                });
            } catch (error) {
                if (error.code === 'EPERM') {
                    return res.status(403).json({ error: '权限不足，无法删除文件夹' });
                }
                throw error;
            }
        } else {
            // 删除文件
            try {
                fs.unlinkSync(normalizedPath);
                res.json({
                    success: true,
                    message: `文件 ${path.basename(normalizedPath)} 已成功删除`
                });
            } catch (error) {
                if (error.code === 'EPERM') {
                    return res.status(403).json({ error: '权限不足，无法删除文件' });
                }
                throw error;
            }
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 新增：编辑会话API (修改文件夹名称)
app.post('/api/edit-session', (req, res) => {
    try {
        const { sessionId, newName } = req.body;

        if (!sessionId || !newName) {
            return res.status(400).json({ error: '会话ID和新名称不能为空' });
        }

        // 查找会话文件夹
        const sessionFolder = path.join(USER_FOLDER, sessionId);
        const sessionFile = path.join(sessionFolder, 'session.json');

        if (!fs.existsSync(sessionFile)) {
            return res.status(404).json({ error: '会话不存在' });
        }

        // 读取会话数据
        const sessionData = JSON.parse(fs.readFileSync(sessionFile, 'utf-8'));

        // 获取原始文件夹路径
        const oldFolderPath = sessionData.folderPath;

        // 检查文件夹是否存在
        if (!fs.existsSync(oldFolderPath)) {
            return res.status(404).json({ error: '关联的文件夹不存在' });
        }

        // 获取文件夹的父路径
        const parentPath = path.dirname(oldFolderPath);

        // 构建新的文件夹路径
        const newFolderPath = path.join(parentPath, newName);

        // 检查新名称的文件夹是否已存在
        if (fs.existsSync(newFolderPath)) {
            return res.status(400).json({ error: '该名称的文件夹已存在' });
        }

        // 重命名文件夹
        try {
            fs.renameSync(oldFolderPath, newFolderPath);
        } catch (error) {
            if (error.code === 'EPERM') {
                return res.status(403).json({ error: '权限不足，无法重命名文件夹' });
            }
            throw error;
        }

        // 更新会话数据
        sessionData.folderPath = newFolderPath;

        // 重新读取文件夹结构
        sessionData.structure = readFolderStructure(newFolderPath);

        // 保存更新后的会话数据
        fs.writeFileSync(
            sessionFile,
            JSON.stringify(sessionData, null, 2),
            'utf-8'
        );

        res.json({
            success: true,
            message: '会话更新成功',
            newFolderPath
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 新增：删除会话API (只删除会话记录，不删除实际文件)
app.post('/api/delete-session', (req, res) => {
    try {
        const { sessionId } = req.body;

        if (!sessionId) {
            return res.status(400).json({ error: '会话ID不能为空' });
        }

        const sessionFolder = path.join(USER_FOLDER, sessionId);

        if (!fs.existsSync(sessionFolder) || !fs.statSync(sessionFolder).isDirectory()) {
            return res.status(404).json({ error: '会话不存在' });
        }

        // 删除会话文件夹及其所有内容
        try {
            deleteFolderRecursive(sessionFolder);
            res.json({ success: true, message: '会话已成功删除' });
        } catch (error) {
            if (error.code === 'EPERM') {
                return res.status(403).json({ error: '权限不足，无法删除会话文件夹' });
            }
            throw error;
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 辅助函数：复制文件夹
function copyDirectory(source, target) {
    // 确保目标文件夹存在
    fs.mkdirSync(target, { recursive: true });
    
    // 读取源文件夹中的所有文件和文件夹
    const files = fs.readdirSync(source);
    
    files.forEach(file => {
        const sourcePath = path.join(source, file);
        const targetPath = path.join(target, file);
        
        const stats = fs.statSync(sourcePath);
        
        if (stats.isDirectory()) {
            // 如果是文件夹，递归复制
            copyDirectory(sourcePath, targetPath);
        } else {
            // 如果是文件，直接复制
            fs.copyFileSync(sourcePath, targetPath);
        }
    });
}

// 辅助函数：简单的字符串哈希函数
function hash(str) {
    let hash = 0;
    if (str.length === 0) return hash;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // 转换为32位整数
    }
    return Math.abs(hash);
}

// 启动服务器
if (import.meta.url === new URL(import.meta.url).href) {
    console.log(`服务器运行在 http://${host}:${PORT}`);
    app.listen(PORT, host, () => {
        console.log(`服务器已启动: http://${host}:${PORT}`);
    });
}

export default app;