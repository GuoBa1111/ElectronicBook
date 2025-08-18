<script setup>
import { ref, onMounted, defineComponent, watch } from 'vue'
// 导入ElMessage
import { ElMessage, ElTooltip } from 'element-plus'
import { SERVER_CONFIG } from '../../config.js'  // 导入配置

const props = defineProps({
  initialFiles: { type: Array, default: () => [] },
  readOnly: { type: Boolean, default: false },
  // 添加folderPath属性
  folderPath: { type: String, default: '' }
})

// 文件系统数据
const files = ref([])
const selectedFile = ref(null)
const currentFolder = ref('未选择文件夹')
const folderPathInput = ref('')
const expandedFolders = ref({})

// emits: ['file-select']
const emit = defineEmits(['file-select'])

// 监听初始数据变化
watch(() => props.initialFiles, (newVal) => {
  if (newVal && newVal.length) {
    // 添加排序逻辑，确保按创建时间升序排列
    const sortedFiles = sortFilesByCreationTime(newVal);
    files.value = sortedFiles
    // 如果有folderPath，优先使用folderPath设置currentFolder
    if (props.folderPath) {
      currentFolder.value = props.folderPath.split('\\').pop()
    } else {
      currentFolder.value = '已加载文件夹'
    }
  }
}, {
  immediate: true
})

// 监听folderPath变化
watch(() => props.folderPath, (newVal) => {
  if (newVal) {
    currentFolder.value = newVal.split('\\').pop()
  }
}, {
  immediate: true
})



// 切换文件夹展开状态
const toggleFolder = (folderId) => {
  expandedFolders.value = {
    ...expandedFolders.value,
    [folderId]: !expandedFolders.value[folderId]
  }
}

// 选择文件或切换文件夹展开状态
const handleFileClick = (file) => {
  // 无论文件还是文件夹，都设置选中状态
  selectedFile.value = file;
  
  if (file.type === 'folder') {
    toggleFolder(file.id);
  } else {
    selectFile(file);
  }
};

// 选择文件
const selectFile = async (file) => {
  if (file.type === 'file') {
    // 查找并更新files数组中的对应文件
    const updateFileInTree = (filesArray) => {
      for (let i = 0; i < filesArray.length; i++) {
        if (filesArray[i].id === file.id) {
          filesArray[i] = { ...filesArray[i], ...file };
          return true;
        }
        if (filesArray[i].children && filesArray[i].children.length) {
          if (updateFileInTree(filesArray[i].children)) {
            return true;
          }
        }
      }
      return false;
    };

    updateFileInTree(files.value);
    selectedFile.value = file;

    try {
      // 调用后端API获取文件内容
      const response = await fetch(
        `${SERVER_CONFIG.baseUrl}/api/file-content?filePath=${encodeURIComponent(file.filePath)}`
      )

      if (!response.ok) {
        throw new Error('获取文件内容失败')
      }

      const data = await response.json()
      // 确保即使文件为空也设置content属性
      file.content = data.content || ''
      emit('file-select', file)
    } catch (error) {
      console.error('Error:', error)
      alert('获取文件内容失败: ' + error.message)
      // 即使获取失败，也触发事件，防止UI卡住
      file.content = ''
      emit('file-select', file)
    }
  }
};

// 定义递归组件
const FileTree = defineComponent({
  name: 'FileTree',
  props: {
    files: Array,
    expandedFolders: Object,
    selectedFile: Object,
    selectedStyle: Object  // 添加这个prop
  },
  emits: ['file-click'],
  setup(props, { emit }) {
    return {
      handleClick: (file) => {
        emit('file-click', file)
      }
    }
  },
  template: `
    <div>
      <div v-for="file in files" :key="file.id" class="file-item">
        <div @click="handleClick(file)" :class="{ 'selected': selectedFile?.id === file.id }"
             :style="selectedFile?.id === file.id ? selectedStyle : {}">
          <span v-if="file.type === 'folder'">
            {{ expandedFolders[file.id] ? '📂' : '📁' }}
          </span>
          <span v-else>📄</span>
          {{ file.name }}
        </div>
        <!-- 子文件夹内容 -->
        <FileTree
          v-if="file.type === 'folder' && expandedFolders[file.id]"
          :files="file.children || []"
          :expandedFolders="expandedFolders"
          :selectedFile="selectedFile"
          :selectedStyle="selectedStyle" 
          @file-click="handleClick"
          class="sub-folder"
        />
      </div>
    </div>
  `
})

// 初始加载
onMounted(() => {
  if (props.initialFiles && props.initialFiles.length) {
    files.value = props.initialFiles
    console.log('初始文件数据已加载')
  }
  // 删除默认加载文件夹的代码
});
// 添加文件操作相关函数
const fileInput = ref(null)

// 添加选中样式定义
const selectedStyle = {
  backgroundColor: 'rgba(255, 255, 255, 0.9)',
  border: '2px solid var(--primary-color)',
  borderRadius: '6px',
  color: 'var(--primary-color)',
  fontWeight: '550',
  boxShadow: '0 3px 6px rgba(0, 0, 0, 0.15)',
  transition: 'all 0.2s ease',
  outline: 'none'
}

// 辅助函数：确定当前操作路径
const getCurrentOperationPath = () => {
  if (!selectedFile.value) {
    // 确保folderPath始终有值
    if (!props.folderPath) {
      console.error('folderPath is empty, cannot determine operation path')
      return null
    }
    return props.folderPath
  }

  if (selectedFile.value.type === 'folder') {
    return selectedFile.value.filePath
  }

  // 如果选中的是文件，则返回其所在目录
  if (selectedFile.value.type === 'file' && selectedFile.value.filePath) {
    const pathParts = selectedFile.value.filePath.split('\\')
    pathParts.pop() // 移除文件名
    return pathParts.join('\\')
  }
  return props.folderPath || null
}

// 创建新文件
const createNewFile = async () => {
  const fileName = prompt('请输入新文件名 (需以.md结尾)', '新文件.md')
  if (!fileName) return

  // 确保文件以.md结尾
  const normalizedFileName = fileName.endsWith('.md') ? fileName : `${fileName}.md`
  // 获取当前操作路径
  const currentPath = getCurrentOperationPath()
  // 添加对currentPath的验证
  if (!currentPath) {
    alert('无法确定创建文件的位置，请先选择一个文件夹或刷新页面重试')
    return
  }

  try {
    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/create-file`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        folderPath: currentPath,
        fileName: normalizedFileName
      })
    })

    if (!response.ok) {
      // 获取服务器返回的错误详情
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.error || '创建文件失败')
    }

    await response.json();
    ElMessage.success('文件创建成功');
    // 刷新文件树
    refreshFileTree();
  } catch (error) {
    console.error('创建文件错误:', error)
    alert('创建文件失败: ' + error.message)
  }
}

// 创建新文件夹
const createNewFolder = async () => {
  const folderName = prompt('请输入新文件夹名', '新文件夹')
  if (!folderName) return

  // 获取当前操作路径
  const currentPath = getCurrentOperationPath()

  try {
    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/create-folder`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        parentPath: currentPath,
        folderName: folderName
      })
    })

    if (!response.ok) {
      throw new Error('创建文件夹失败')
    }

    await response.json();
    ElMessage.success('文件夹创建成功');
    // 刷新文件树
    refreshFileTree();
  } catch (error) {
    console.error('创建文件夹错误:', error)
    alert('创建文件夹失败: ' + error.message)
  }
}

// 触发文件上传
const uploadFile = () => {
  fileInput.value.click()
}

// 新添加：递归按创建时间排序文件的函数
const sortFilesByCreationTime = (filesArray) => {
  if (!Array.isArray(filesArray)) return [];
  
  // 直接按创建时间升序排列，不考虑类型
  const sorted = [...filesArray].sort((a, b) => {
    const timeA = new Date(a.createdAt).getTime();
    const timeB = new Date(b.createdAt).getTime();
    return timeA - timeB;
  });
  
  // 递归对每个文件夹的子项目进行排序
  return sorted.map(item => {
    if (item.type === 'folder' && item.children && item.children.length) {
      return {
        ...item,
        children: sortFilesByCreationTime(item.children)
      };
    }
    return item;
  });
};

// 处理文件上传
const handleFileUpload = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  // 确保文件以.md结尾
  if (!file.name.endsWith('.md')) {
    alert('只能上传.md文件')
    return
  }

  // 获取当前操作路径
  const currentPath = getCurrentOperationPath()
  if (!currentPath) {
    alert('无法确定上传位置，请先选择一个文件夹')
    return
  }

  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('folderPath', currentPath)

    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/upload-file`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error('文件上传失败')
    }

    await response.json();
    // 替换alert为ElMessage.success
    ElMessage.success('文件上传成功');
    // 刷新文件树
    refreshFileTree();
    // 重置文件输入
    fileInput.value.value = ''
  } catch (error) {
    console.error('文件上传错误:', error)
    alert('文件上传失败: ' + error.message)
  }
}
// 添加刷新文件树的函数
const refreshFileTree = async () => {
  try {
    // 保存当前状态 (使用文件路径作为键)
    const savedExpandedPaths = {};
    // 递归收集展开的文件夹路径
    const collectExpandedPaths = (filesArray) => {
      filesArray.forEach(file => {
        if (file.type === 'folder' && expandedFolders.value[file.id]) {
          savedExpandedPaths[file.filePath] = true;
        }
        if (file.children && file.children.length) {
          collectExpandedPaths(file.children);
        }
      });
    };
    collectExpandedPaths(files.value);

    // 保存选中文件的路径
    const savedSelectedFilePath = selectedFile.value?.filePath;

    // 获取当前会话的文件夹路径
    const folderPath = props.folderPath || getCurrentOperationPath();
    if (!folderPath) {
      console.error('无法确定文件夹路径，刷新失败');
      return;
    }

    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/read-folder`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        folderPath: folderPath
      })
    });

    if (!response.ok) {
      throw new Error('刷新文件树失败');
    }

    const newFiles = await response.json();
    
    // 添加排序逻辑，确保按创建时间升序排列
    const sortedFiles = sortFilesByCreationTime(newFiles);

    // 更新文件树
    files.value = sortedFiles;

    // 恢复展开/折叠状态
    const restoreExpandedState = (filesArray) => {
      filesArray.forEach(file => {
        // 如果是文件夹且在保存的路径中存在
        if (file.type === 'folder' && savedExpandedPaths[file.filePath]) {
          expandedFolders.value[file.id] = true;
        }
        // 递归处理子文件夹
        if (file.children && file.children.length) {
          restoreExpandedState(file.children);
        }
      });
    };

    // 恢复选中文件
    const restoreSelectedFile = (filesArray) => {
      for (let i = 0; i < filesArray.length; i++) {
        const file = filesArray[i];
        // 通过filePath匹配
        if (file.filePath === savedSelectedFilePath) {
          selectedFile.value = file;
          return true;
        }
        // 递归查找子文件夹
        if (file.children && file.children.length) {
          if (restoreSelectedFile(file.children)) {
            return true;
          }
        }
      }
      return false;
    };

    // 恢复展开状态
    restoreExpandedState(files.value);

    // 恢复选中文件
    if (savedSelectedFilePath) {
      restoreSelectedFile(files.value);
    }
  } catch (error) {
    console.error('刷新文件树错误:', error);
    alert('刷新文件树失败: ' + error.message);
  }
};

// 添加折叠所有文件夹的函数
const collapseAllFolders = () => {
  // 清空expandedFolders对象，所有文件夹都将折叠
  expandedFolders.value = {};
};

// 添加删除文件/文件夹的函数
const deleteSelectedItem = async () => {
  if (!selectedFile.value) {
    alert('请先选择要删除的文件或文件夹');
    return;
  }

  const isConfirmed = confirm(`确定要删除 ${selectedFile.value.name} ${selectedFile.value.type === 'folder' ? '文件夹' : '文件'} 吗？`);
  if (!isConfirmed) return;

  try {
    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/delete-item`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        filePath: selectedFile.value.filePath,
        isFolder: selectedFile.value.type === 'folder'
      })
    });

    if (!response.ok) {
      throw new Error('删除失败');
    }

    await response.json();
    // 替换alert为ElMessage.success
    ElMessage.success('删除成功');
    // 刷新文件树
    refreshFileTree();
    // 清除选中状态
    selectedFile.value = null;
  } catch (error) {
    console.error('删除错误:', error);
    alert('删除失败: ' + error.message);
  }
};
// 添加处理空白区域点击的函数
const handleBlankClick = (event) => {
  // 检查点击目标是否是file-list元素本身
  if (event.target.classList.contains('file-list')) {
    selectedFile.value = null;
  }
};
</script>

<template>
  <div class="file-explorer">
    <div class="file-explorer-header" v-if="!readOnly">
      <div class="header-content">
        <div class="header-title-and-tools">
          <h3>文件浏览器</h3>
          <!-- 将工具栏移到标题右侧 -->
          <div class="file-operations-toolbar">
            <ElTooltip content="新建文件" placement="top" :show-after="500">
              <button class="toolbar-btn" @click="createNewFile">
                <span class="icon">📄</span> 
              </button>
            </ElTooltip>
            <ElTooltip content="新建文件夹" placement="top" :show-after="500">
              <button class="toolbar-btn" @click="createNewFolder">
                <span class="icon">📁</span> 
              </button>
            </ElTooltip>
            <ElTooltip content="上传文件" placement="top" :show-after="500">
              <button class="toolbar-btn" @click="uploadFile">
                <span class="icon">⬆️</span> 
              </button>
            </ElTooltip>
            <ElTooltip content="删除" placement="top" :show-after="500">
              <button class="toolbar-btn" @click="deleteSelectedItem">
                <span class="icon">🗑️</span> 
              </button>
            </ElTooltip>
            <ElTooltip content="折叠" placement="top" :show-after="500">
              <button class="toolbar-btn" @click="collapseAllFolders">
                <span class="icon">📚</span> 
              </button>
            </ElTooltip>
          </div>
        </div>
        <div class="current-folder">当前: {{ currentFolder }}</div>
      </div>
    </div>
    <div v-else class="file-explorer-header-readonly">
      <div class="header-content">
        <h3>文件浏览器 (只读)</h3>
      </div>
    </div>
    <div class="file-list" @click="handleBlankClick">
      <!-- 使用递归组件渲染文件树 -->
      <FileTree :files="files" :expandedFolders="expandedFolders" :selectedFile="selectedFile" :selectedStyle="selectedStyle" @file-click="handleFileClick" />
      <!-- 空状态提示 -->
      <div v-if="files.length === 0" class="empty-state">
        <div class="empty-icon">📁</div>
        <div class="empty-message">未选择文件夹或文件夹为空</div>
        <template v-if="!readOnly">
          <div class="empty-hint">请通过首页创建或选择会话</div>
        </template>
      </div>
    </div>
    <!-- 移除原来底部的工具栏 -->
    <input type="file" ref="fileInput" class="hidden-file-input" @change="handleFileUpload" accept=".md">
  </div>
</template>

<style scoped src="./FileExplorer.css"></style>

