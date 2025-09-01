<script setup>
import { ref, inject, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'  // 修改：添加useRouter导入
import FileExplorer from '../components/FileExplorer.vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()  // 添加：创建router实例
const sessionId = ref(route.params.id)
const editorRef = ref(null)
const Vditor = inject('Vditor')
const currentFile = ref(null)
const isEditorContentChanged = ref(false)
const folderStructure = ref([])
const folderPath = ref('')

// 监听路由参数变化
watch(() => route.params.id, (newId) => {
  if (newId) {
    sessionId.value = newId
    loadSessionData()
  }
})

// 添加：返回主界面函数
const goToHome = () => {
  router.push('/')
}

const previewBook = () => {
  const previewUrl = `/web/${sessionId.value}/_book`;
  window.open(previewUrl, '_blank');
}

// 加载会话数据
const loadSessionData = async () => {
  try {
    const response = await fetch(`/api/get-folder-session?id=${sessionId.value}`)
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`会话ID '${sessionId.value}' 不存在`)
      } else {
        throw new Error('加载会话失败')
      }
    }
    const data = await response.json()
    folderStructure.value = data.structure
    folderPath.value = data.folderPath

    // 确保folderPath有值
    if (!folderPath.value) {
      throw new Error('获取的会话数据中没有有效的文件夹路径')
    }
  } catch (error) {
    console.error('加载会话错误:', error)
    ElMessage({
      message: '无法加载会话: ' + error.message,
      type: 'error'
    })
    // 重定向到首页
    router.push('/')
  }
}

// 处理文件选择事件
const handleFileSelect = (file) => {
  currentFile.value = file;
  if (editorRef.value) {
    editorRef.value.setValue(file.content || '');
    isEditorContentChanged.value = false;
  }
}

// 保存文件内容到后端
const saveFileToBackend = async () => {
  if (!currentFile.value || !isEditorContentChanged.value) {
    return;
  }

  try {
    const response = await fetch(`/api/save-file`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        filePath: currentFile.value.filePath,
        content: editorRef.value.getValue()
      })
    });

    if (!response.ok) {
      throw new Error('保存文件失败');
    }

    const data = await response.json();

    isEditorContentChanged.value = false;
    ElMessage({
      message: '保存成功!',
      type: 'success',
      duration: 1000
    });
    

  } catch (error) {
    console.error('保存文件错误:', error);
    ElMessage({
      message: '保存失败: ' + error.message,
      type: 'error'
    })
  }
}

//发布电子书
const exportBook = async () => {
  try {
    const loadingMessage = ElMessage({
      message: '正在发布...',
      type: 'info',
      showClose: false
    });

    const response = await fetch(`/api/export-book`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        sessionId: sessionId.value
      })
    });


    if (!response.ok) {
      loadingMessage.close();
      throw new Error('发布失败')
    }

    const data = await response.json();
    if (data.success) {
      ElMessage({
        message: '发布成功!',
        type: 'success',
        duration: 3000
      });
      loadingMessage.close();
    } else {
      ElMessage({
        message: '发布失败: ' + data.error,
        type: 'error'
      });
      loadingMessage.close();
    }
  } catch (error) {
    if (loadingMessage) {
      loadingMessage.close();
    }
    console.error('发布错误:', error);
    ElMessage({
      message: '发布失败: ' + error.message,
      type: 'error'
    });
  }
}

const handleExportSummary = async () => {
  try {
    const response = await fetch(`/api/export-summary`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        sessionId: route.params.id
      })
    });
    
    if (!response.ok) {
      throw new Error('导出目录请求失败');
    }
    
    const data = await response.json();
    
    if (data.success) {
      ElMessage.success('目录已成功导出到 SUMMARY.md');
    } else {
      ElMessage.error(data.error || '导出目录失败');
    }
  } catch (error) {
    console.error('导出目录失败:', error);
    ElMessage.error('导出目录失败，请重试');
  }
}
//导出pdf
const exportPDF = async () => {
  try {
    const loadingMessage = ElMessage({
      message: '正在生成PDF...',
      type: 'info',
      showClose: false
    });

    const response = await fetch(`/api/export-pdf`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        sessionId: sessionId.value
      })
    });

    loadingMessage.close();

    if (response.ok) {
      // 直接触发下载
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // 从响应头获取文件名，如果没有则使用默认名
      const contentDisposition = response.headers.get('content-disposition');

      let fileName = '电子书.pdf';
      if (contentDisposition) {
        const matches = /filename=([^;]+)/i.exec(contentDisposition);

        if (matches && matches[1]) {
          // 获取捕获组1的内容，并去除可能存在的双引号
          fileName = matches[1].replace(/^"|"$/g, '');
        }
      }
      
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      
      // 清理
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      ElMessage({
        message: 'PDF导出成功!',
        type: 'success',
        duration: 3000
      });
    } else {
      const errorData = await response.json();
      throw new Error(errorData.error || 'PDF导出失败');
    }
  } catch (error) {
    console.error('导出PDF错误:', error);
    ElMessage({
      message: 'PDF导出失败: ' + error.message,
      type: 'error'
    });
  }
}

onMounted(async () => {
  await loadSessionData()

  // 先创建一个标志，表示是否需要清空编辑器
  let shouldClearEditor = true;

  editorRef.value = new Vditor('editor', {
    height: '100%',
    width: '100%',
    mode: 'sv',
    preview: {
      delay: 0
    },
    upload: {
      url: `/api/upload-image`,
      fieldName: 'file[]',
      maxSize: 1024 * 1024 * 10, // 10MB
      accept: 'image/*',
      multiple: false,
      // 上传成功回调
      success: (editor, result) => {
        console.log('上传结果:', result);
        try {
          const res = JSON.parse(result);
          if (res.code === 0) {
            if (Object.keys(res.data.succMap).length > 0) {
              // 获取第一个成功上传的图片URL
              const firstFileName = Object.keys(res.data.succMap)[0];
              const imageUrl = res.data.succMap[firstFileName];
              // 插入图片到编辑器 - 使用insertValue方法
              //const imgMarkdown = `![图片](${imageUrl})`

              editorRef.value.insertValue('<', true);
              editorRef.value.insertValue('img src=', true);
              editorRef.value.insertValue(imageUrl, true);
              editorRef.value.insertValue(' width=400 height=400>', true);
              ElMessage({ message: '图片上传成功', type: 'success' });
            } else if (res.data.errFiles && res.data.errFiles.length > 0) {
              ElMessage({ message: `图片上传失败: ${res.data.errFiles.join(', ')}`, type: 'error' });
            } else {
              ElMessage({ message: '图片上传失败: 未知错误', type: 'error' });
            }
          } else {
            ElMessage({ message: '图片上传失败: ' + (res.msg || '服务器错误'), type: 'error' });
          }
        } catch (e) {
          console.error('解析上传结果失败:', e);
          ElMessage({ message: '图片上传失败: 服务器返回格式错误', type: 'error' });
        }
      },
      // 上传错误回调
      error: (editor, err) => {
        console.error('上传错误:', err);
        ElMessage({ message: '图片上传失败: ' + (err || '网络错误'), type: 'error' });
      }
    },
    input: (value) => {
      if (currentFile.value) {
        currentFile.value.content = value;
        isEditorContentChanged.value = true;
      }
    },
    ready: () => {
      // 第一次 ready 时清空
      if (shouldClearEditor) {
        editorRef.value.setValue('');
        shouldClearEditor = false;
      }
    }
  });

  // 添加一个额外的延迟清空操作，确保覆盖所有可能的时序问题
  setTimeout(() => {
    if (editorRef.value && shouldClearEditor) {
      editorRef.value.setValue('');
      shouldClearEditor = false;
    }
  }, 300);

  // 监听点击事件，当点击编辑器外部时保存
  document.addEventListener('click', (e) => {
    const editorContainer = document.querySelector('.editor-container');
    if (editorContainer && !editorContainer.contains(e.target)) {
      saveFileToBackend();
    }
  });
});

onUnmounted(() => {
  if (editorRef.value) {
    editorRef.value.destroy();
  }
  document.removeEventListener('click', saveFileToBackend);
});
</script>

<template>
  <div class="app-container">
    <div class="header">
      <h1>电子书籍编辑器</h1>
      <div class="folder-info">
        <span class="folder-path">{{ folderPath }}</span>
      </div>
    </div>
    <div class="session-info">
      <div class="button-group">
        <button class="export-summary-btn" @click="handleExportSummary">①导出目录</button>
        <button class="export-btn" @click="exportBook">②保存并发布</button>
        <button class="preview-btn" @click="previewBook">③预览</button>
        <button class="back-btn" @click="goToHome">返回主界面</button>
      </div>
    </div>
    <div class="main-layout">
      <div class="file-explorer-container">
        <FileExplorer 
          @file-select="handleFileSelect" 
          :initial-files="folderStructure" 
          :read-only="false"
          :folder-path="folderPath" 
        />
      </div>
      <div class="splitter"></div>
      <div class="editor-container">
        <div id="editor" ref="editorRef"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 添加CSS变量定义颜色主题 */
:root {
  --primary-color: #4285f4;
  --secondary-color: #34a853;
  --accent-color: #fbbc05;
  --text-color: #333333;
  --light-text: #5f6368;
  --background-color: #ffffff;
  --light-background: #f8f9fa;
  --border-color: #dadce0;
  --shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.app-container {
  max-width: 100%;
  margin: 0;
  padding: 0;
  height: 100vh;
  background-color: var(--background-color);
  color: var(--text-color);
  display: flex;
  flex-direction: column;
}

/* 优化标题区域 */
.header {
  background-color: var(--primary-color);
  color: white;
  padding: 15px 20px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: black;
  display: flex;
  align-items: center;
  gap: 10px;
}

.folder-info {
  font-size: 14px;
  opacity: 0.9;
}

.folder-path {
  font-family: 'Courier New', Courier, monospace;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  color: black;
}

.session-info {
  margin: 15px 20px;
  padding: 12px 16px;
  background-color: var(--light-background);
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--shadow);
}

/* 优化链接样式 */
.session-info code {
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
  color: var(--primary-color);
  background-color: rgba(66, 133, 244, 0.1);
  padding: 3px 6px;
  border-radius: 4px;
}

.button-group {
  display: flex;
  gap: 12px;
  margin-left: auto;
}

/* 优化按钮样式 */
.back-btn, .export-btn, .preview-btn, .export-summary-btn, .pdf-btn {

  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
  background-color: gray;
  color: white;
}



.back-btn:hover {
  background-color: #3367d6;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.export-btn:hover {
  background-color: #2d9249;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.preview-btn:hover {
  background-color: #db3636;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.export-summary-btn:hover {
  background-color: #c9c757;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.pdf-btn:hover {
  background-color: #df633d;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}


.main-layout {
  display: flex;
  flex: 1;
  margin: 0 20px 20px 20px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow);
}

.file-explorer-container {
  width: 300px;
  min-width: 250px;
  max-width: 400px;
  border-right: 1px solid var(--border-color);
  background-color: var(--light-background);
}

.splitter {
  width: 5px;
  background-color: var(--border-color);
  cursor: ew-resize;
  flex-shrink: 0;
}

.editor-container {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
  background-color: white;
}

.success-message {
  position: fixed;
  top: 20px;
  right: 20px;
  background-color: var(--secondary-color);
  color: white;
  padding: 10px 20px;
  border-radius: 4px;
  box-shadow: var(--shadow);
  z-index: 1000;
  transition: opacity 0.3s;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .main-layout {
    flex-direction: column;
  }

  .file-explorer-container {
    width: 100%;
    max-width: 100%;
    height: 300px;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .splitter {
    display: none;
  }
}
</style>