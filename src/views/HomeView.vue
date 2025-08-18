<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { SERVER_CONFIG } from '../../config.js'  // 导入配置
import { ElMessage } from 'element-plus'

const folderNameInput = ref('')  // 改为文件夹名称输入
const router = useRouter()
const sessions = ref([])  // 新增：存储会话列表

// 新增：获取路径中的最后一个文件夹名
const getLastFolderName = (path) => {
  // 处理Windows路径分隔符
  const parts = path.split('\\');
  // 如果最后一个部分是空（路径以\结尾），则取倒数第二个
  if (parts[parts.length - 1] === '') {
    return parts[parts.length - 2];
  }
  return parts[parts.length - 1];
}


// 新增：获取所有会话
const getAllSessions = async () => {
  try {
    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/get-all-sessions`)
    if (!response.ok) {
      throw new Error('获取会话列表失败')
    }
    const data = await response.json()
    // 按创建时间升序排序
    sessions.value = data.sessions.sort((a, b) => {
      return new Date(a.createdAt) - new Date(b.createdAt)
    })
  } catch (error) {
    console.error('获取会话列表错误:', error)
  }
}

// 新增：页面加载时获取会话列表
onMounted(() => {
  getAllSessions()
})

// 读取文件夹并生成唯一ID
const readFolder = async () => {
  if (!folderNameInput.value.trim()) {
    ElMessage.error('请输入文件夹名称') 
    return
  }

  const loadingMessage = ElMessage({  
    message: '文件夹创建中，请稍候...',
    type: 'loading',
    duration: 0,  // 不自动关闭
    showClose: false,
    style: {
      backgroundColor: '#4a90e2',
      color: 'white'
    },
  })

  try {
    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/create-website-session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        folderName: folderNameInput.value.trim()
      })
    })

    if (!response.ok) {
      throw new Error('创建会话失败')
    }

    const data = await response.json()
    loadingMessage.close()  // 关闭加载提示

    ElMessage.success('文件夹创建成功，正在跳转...')  // 显示成功提示
    // 跳转到编辑器页面
    router.push({ name: 'editor', params: { id: data.sessionId } })
  } catch (error) {
    console.error('Error:', error)
    loadingMessage.close()  // 关闭加载提示
    ElMessage.error('处理文件夹失败: ' + error.message)  // 显示错误提示
  }
}

// 新增：点击会话跳转
const goToSession = (sessionId) => {
  router.push({ name: 'editor', params: { id: sessionId } })
}

// 新增：编辑会话名称
const editSession = async (session) => {
  const currentName = getLastFolderName(session.folderPath)
  const newName = prompt('请输入新的文件夹名称:', currentName)
  if (newName !== null && newName.trim() !== '') {
    try {
      const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/edit-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          sessionId: session.sessionId,
          newName: newName
        })
      })
      if (!response.ok) {
        throw new Error('更新会话名称失败')
      }
      // 更新本地会话列表
      getAllSessions()
    } catch (error) {
      console.error('编辑会话错误:', error)
      alert('编辑会话失败: ' + error.message)
    }
  }
}

// 新增：删除会话
const deleteSession = async (session) => {
  if (confirm('确定要删除这个文件夹会话吗?')) {
    try {
      const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/delete-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          sessionId: session.sessionId
        })
      })
      if (!response.ok) {
        throw new Error('删除会话失败')
      }
      // 更新本地会话列表
      getAllSessions()
    } catch (error) {
      console.error('删除会话错误:', error)
      alert('删除会话失败: ' + error.message)
    }
  }
}

// 新增：预览会话
const previewSession = (session) => {
  const previewUrl = `http://${SERVER_CONFIG['host']}/${session.sessionId}/_book`;
  window.open(previewUrl, '_blank');
}

</script>
<template>
  <div class="home-container">
    <!-- 添加顶部导航栏 -->
    <header class="header">
      <div class="logo">
        <svg class="icon" viewBox="0 0 1024 1024" width="32" height="32" fill="currentColor">
          <path d="M832 64H192c-17.7 0-32 14.3-32 32v832c0 17.7 14.3 32 32 32h640c17.7 0 32-14.3 32-32V96c0-17.7-14.3-32-32-32zm-40 824H232V136h560v752zM464 480c0 4.4-3.6 8-8 8h-64c-4.4 0-8-3.6-8-8v-64c0-4.4 3.6-8 8-8h64c4.4 0 8 3.6 8 8v64zm0 192c0 4.4-3.6 8-8 8h-64c-4.4 0-8-3.6-8-8v-64c0-4.4 3.6-8 8-8h64c4.4 0 8 3.6 8 8v64zm192-192c0 4.4-3.6 8-8 8h-64c-4.4 0-8-3.6-8-8v-64c0-4.4 3.6-8 8-8h64c4.4 0 8 3.6 8 8v64zm0 192c0 4.4-3.6 8-8 8h-64c-4.4 0-8-3.6-8-8v-64c0-4.4 3.6-8 8-8h64c4.4 0 8 3.6 8 8v64z"></path>
        </svg>
        <span>电子书籍编辑器</span>
      </div>
    </header>

    <div class="content-wrapper">
      <div class="sidebar">
        <div class="sidebar-header">
          <h2>已有的文件夹</h2>
          <div class="divider"></div>
        </div>
        <ul class="session-list">
          <li v-for="session in sessions" :key="session.sessionId"
              @click="goToSession(session.sessionId)" class="session-item">
            <svg class="folder-icon" viewBox="0 0 1024 1024" width="20" height="20" fill="currentColor">
              <path d="M928 224H832v-64c0-17.7-14.3-32-32-32H192c-17.7 0-32 14.3-32 32v576c0 17.7 14.3 32 32 32h192v64c0 17.7 14.3 32 32 32h384c17.7 0 32-14.3 32-32v-64h96c17.7 0 32-14.3 32-32V256c0-17.7-14.3-32-32-32zM896 800h-64v-64c0-17.7-14.3-32-32-32H320c-17.7 0-32 14.3-32 32v64H160V160h576v64h160v576z"></path>
            </svg>
            <div class="session-path">{{ getLastFolderName(session.folderPath) }}</div>
            <div class="session-actions">
              <button @click.stop="previewSession(session)" class="preview-btn">👁️</button>
              <button @click.stop="editSession(session)" class="edit-btn">✏️</button>
              <button @click.stop="deleteSession(session)" class="delete-btn">🗑️</button>
            </div>
          </li>
        </ul>
        <div class="empty-state" v-if="sessions.length === 0">
          <p>暂无已保存的文件夹会话</p>
          <p class="hint">请在右侧输入路径创建新会话</p>
        </div>
      </div>

      <div class="main-content">
        <div class="card">
          <h1>欢迎使用电子书籍编辑器</h1>
          <p class="subtitle">通过输入文件夹名称创建或打开电子书项目</p>
          <div class="folder-input-section">
            <input
              v-model="folderNameInput"
              type="text"
              placeholder="输入文件夹名称"
              class="folder-path-input"
              id="folderName"
              name="folderName"
            >
            <button @click="readFolder" class="read-folder-btn">
              <svg class="btn-icon" viewBox="0 0 1024 1024" width="18" height="18" fill="currentColor">
                <path d="M909.6 370.7L840 301.1c-5.3-5.3-13.7-5.3-19 0l-256 256c-5.3 5.3-5.3 13.7 0 19l256 256c5.3 5.3 13.7 5.3 19 0l69.6-69.6c5.3-5.3 5.3-13.7 0-19L660.1 518.3c-5.3-5.3-5.3-13.7 0-19L909.6 370.7zM537.4 518.3L281.4 262.3c-5.3-5.3-13.7-5.3-19 0L192 334.1c-5.3 5.3-5.3 13.7 0 19l256 256c5.3 5.3 13.7 5.3 19 0l69.6-69.6c5.3-5.3 5.3-13.7 0-19L537.4 518.3z"></path>
              </svg>
              打开/创建项目
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 全局样式变量 */
:root {
  --primary-color: #4285f4;
  --primary-light: #e8f0fe;
  --secondary-color: #34a853;
  --text-color: #333;
  --text-light: #666;
  --border-color: #eee;
  --background-color: #f8f9fa;
  --card-bg: #fff;
  --hover-color: #f5f5f5;
  --sidebar-width: 450px;
  --loading-bg: #4a90e2;  
}



.home-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 1400px;
  margin: 0 auto;
  overflow: hidden;
  box-sizing: border-box;
  background-color: var(--background-color);
}

/* 顶部导航栏 */
.header {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  background-color: var(--card-bg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.logo {
  display: flex;
  align-items: center;
  color: var(--primary-color);
  font-size: 18px;
  font-weight: 600;
}

.logo .icon {
  margin-right: 8px;
}

.content-wrapper {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar {
  width:  350px ;
  background-color: var(--card-bg);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: all 0.3s;
  overflow-y: auto;
}

.sidebar-header {
  padding: 20px;
  position: sticky;
  top: 0;
  background-color: var(--card-bg);
  z-index: 5;
}

.sidebar-header h2 {
  margin: 0;
  font-size: 18px;
  color: var(--text-color);
}

.divider {
  height: 1px;
  background-color: var(--border-color);
  margin-top: 16px;
}

.session-list {
  list-style: none;
  padding: 0 20px 20px;
  margin: 0;
  flex: 1;
}

.session-item {
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  background-color: var(--card-bg);
  border: 1px solid var(--border-color);
  width: 100%; /* 确保会话项宽度固定 */
  box-sizing: border-box; /* 包含padding和border在宽度内 */
  position: relative;
}

.session-item:hover {
  background-color: var(--primary-light);
  border-color: var(--primary-color);
  transform: translateX(4px);
}

.folder-icon {
  margin-right: 12px;
  color: #ff9800;
}

.session-path {
  font-size: 16px;
  color: var(--text-color);
  word-break: break-all;
  flex: 1;
}

/* 新增：会话操作按钮样式 */
.session-actions {
  display: none; /* 保持隐藏，只在悬停时显示 */
  position: absolute; /* 使用绝对定位 */
  right: 16px; /* 固定在右侧 */
  top: 50%; /* 垂直居中 */
  transform: translateY(-50%); /* 精确垂直居中 */
  gap: 8px;
  white-space: nowrap;
}


.session-item:hover .session-actions {
  display: flex;
}

.preview-btn, .edit-btn, .delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.edit-btn:hover, .delete-btn:hover, .preview-btn:hover {
  background-color: var(--hover-color);
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-light);
}

.empty-state .hint {
  font-size: 14px;
  margin-top: 8px;
}

.main-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  overflow: auto;
}

.card {
  width: 100%;
  max-width: 600px;
  background-color: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  padding: 40px;
  text-align: center;
  transition: transform 0.3s;
}

.card:hover {
  transform: translateY(-5px);
}

h1 {
  font-size: 32px;
  color: var(--text-color);
  margin-bottom: 16px;
}

.subtitle {
  font-size: 16px;
  color: var(--text-light);
  margin-bottom: 32px;
}

.folder-input-section {
  display: flex;
  gap: 12px;
  width: 100%;
  margin-top: 20px;
}

.folder-path-input {
  flex: 1;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.folder-path-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(66, 133, 244, 0.2);
}

.read-folder-btn {
  padding: 0 24px;
  background-color: gray;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.3s;
}

.read-folder-btn:hover {
  background-color: #3367d6;
}

.btn-icon {
  margin-right: 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .content-wrapper {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: 30%;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .main-content {
    height: 70%;
    padding: 20px;
  }

  .card {
    padding: 20px;
  }
}
</style>