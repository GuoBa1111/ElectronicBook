import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  base: './', // 确保使用相对路径
  plugins: [
    vue({
      // 启用运行时编译
      runtimeCompiler: true
    })
  ],
  resolve: {
    alias: {
      // 确保Vue使用支持运行时编译的版本
      'vue': 'vue/dist/vue.esm-bundler.js'
    }
  }
})
