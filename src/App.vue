<script setup>

import { SERVER_CONFIG } from '../config.js';  // 导入配置
import { ref, inject, onMounted, onUnmounted, watch } from 'vue'
import FileExplorer from './components/FileExplorer.vue'

const editorRef = ref(null)
const Vditor = inject('Vditor')
const currentFile = ref(null)
const isEditorContentChanged = ref(false)

// 处理文件选择事件
const handleFileSelect = (file) => {
  console.log('选中的文件:', file);
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
    const response = await fetch(`${SERVER_CONFIG.baseUrl}/api/save-file`, {
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
  } catch (error) {
    console.error('保存文件错误:', error);
    alert('保存文件失败: ' + error.message);
  }
}

// 初始化编辑器并设置监听
onMounted(() => {
  editorRef.value = new Vditor('editor', {
    height: '100%',
    width: '100%',
    mode: 'sv',
    preview: {
      delay: 0
    },
    input: (value) => {
      // 当编辑器内容变化时更新currentFile
      if (currentFile.value) {
        currentFile.value.content = value;
        isEditorContentChanged.value = true;
      }
    }
  });

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
  <router-view />
</template>


<style scoped>
.app-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  height: 100vh;
}

.main-layout {
  display: flex;
  height: calc(100% - 50px);
}

.editor-container {
  flex: 1;
  padding: 0 20px;
  display: flex;
  flex-direction: column;
}

.vditor-container {
  flex: 1;
  border: 1px solid #eee;
  border-radius: 4px;
}

.preview-container {
  margin-top: 20px;
  padding: 10px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
}
</style>