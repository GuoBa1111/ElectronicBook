const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = 3000;
const DATA_FOLDER = path.join(__dirname, '..', 'data');

// 确保data文件夹存在
if (!fs.existsSync(DATA_FOLDER)) {
  fs.mkdirSync(DATA_FOLDER, { recursive: true });
}

// 允许跨域
app.use(cors());

// 静态文件服务
app.use(express.static(path.join(__dirname, 'public')));

// 解析JSON请求体
app.use(express.json());

// 创建文件夹会话API
app.post('/api/create-folder-session', (req, res) => {
  const { folderPath } = req.body;

  if (!folderPath) {
    return res.status(400).json({ error: '文件夹路径不能为空' });
  }

  try {
    // 标准化Windows路径
    const normalizedPath = path.resolve(folderPath);

    // 检查路径是否存在
    if (!fs.existsSync(normalizedPath)) {
      return res.status(404).json({ error: '文件夹不存在' });
    }

    // 检查是否是文件夹
    const stats = fs.statSync(normalizedPath);
    if (!stats.isDirectory()) {
      return res.status(400).json({ error: '提供的路径不是文件夹' });
    }

    // 读取文件夹结构
    const structure = readFolderStructure(normalizedPath);

    // 检查是否已存在相同文件夹的会话
    const existingSessions = fs.readdirSync(DATA_FOLDER)
      .filter(file => file.endsWith('.json'))
      .map(file => {
        const data = fs.readFileSync(path.join(DATA_FOLDER, file), 'utf8');
        return JSON.parse(data);
      })
      .filter(session => session.folderPath === normalizedPath);

    // 如果存在相同文件夹的会话，返回已有的sessionId
    if (existingSessions.length > 0) {
      return res.json({ sessionId: existingSessions[0].sessionId });
    }

    // 生成唯一ID
    const sessionId = uuidv4().substring(0, 8);

    // 保存会话数据
    const sessionData = {
      sessionId,
      folderPath: normalizedPath,
      structure,
      createdAt: new Date().toISOString()
    };

    fs.writeFileSync(
      path.join(DATA_FOLDER, `${sessionId}.json`),
      JSON.stringify(sessionData, null, 2),
      'utf8'
    );

    res.json({ sessionId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 获取文件夹会话API
app.get('/api/get-folder-session', (req, res) => {
  const { id } = req.query;

  if (!id) {
    return res.status(400).json({ error: '会话ID不能为空' });
  }

  try {
    // 查找会话文件
    const sessionFile = path.join(DATA_FOLDER, `${id}.json`);

    if (!fs.existsSync(sessionFile)) {
      return res.status(404).json({ error: '会话不存在' });
    }

    // 读取会话数据
    const sessionData = JSON.parse(fs.readFileSync(sessionFile, 'utf8'));

    // 检查文件夹是否仍然存在
    if (!fs.existsSync(sessionData.folderPath)) {
      return res.status(404).json({ error: '关联的文件夹不存在' });
    }

    res.json({
      structure: sessionData.structure,
      folderPath: sessionData.folderPath
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 获取文件夹结构的API
app.post('/api/read-folder', (req, res) => {
  const { folderPath } = req.body;

  if (!folderPath) {
    return res.status(400).json({ error: '文件夹路径不能为空' });
  }

  try {
    // 标准化Windows路径
    const normalizedPath = path.resolve(folderPath);

    // 检查路径是否存在
    if (!fs.existsSync(normalizedPath)) {
      return res.status(404).json({ error: '文件夹不存在' });
    }

    // 检查是否是文件夹
    const stats = fs.statSync(normalizedPath);
    if (!stats.isDirectory()) {
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
  const items = fs.readdirSync(folderPath);
  const structure = [];

  for (const item of items) {
    const itemPath = path.join(folderPath, item);
    const stats = fs.statSync(itemPath);

    if (stats.isDirectory()) {
      // 如果是文件夹，递归读取
      structure.push({
        id: Date.now() + Math.random(),
        name: item,
        type: 'folder',
        children: readFolderStructure(itemPath)
      });
    } else if (stats.isFile() && item.endsWith('.md')) {
      // 只处理md文件
      structure.push({
        id: Date.now() + Math.random(),
        name: item,
        type: 'file',
        filePath: itemPath
      });
    }
  }

  return structure;
}

// 获取文件内容的API
app.get('/api/file-content', (req, res) => {
  const { filePath } = req.query;

  if (!filePath) {
    return res.status(400).json({ error: '文件路径不能为空' });
  }

  try {
    // 检查文件是否存在
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: '文件不存在' });
    }

    // 读取文件内容
    const content = fs.readFileSync(filePath, 'utf8');
    res.json({ content });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 保存文件内容的API
app.post('/api/save-file', (req, res) => {
  const { filePath, content } = req.body;

  if (!filePath) {
    return res.status(400).json({ error: '文件路径不能为空' });
  }

  if (content === undefined) {
    return res.status(400).json({ error: '文件内容不能为空' });
  }

  try {
    // 检查文件是否存在
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: '文件不存在' });
    }

    // 写入文件内容
    fs.writeFileSync(filePath, content, 'utf8');
    res.json({ success: true, message: '文件保存成功' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 启动服务器
app.listen(PORT, () => {
  console.log(`服务器运行在 http://localhost:${PORT}`);
});