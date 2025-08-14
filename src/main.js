// 在顶部添加引入语句
import './global.css'

import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import Vditor from 'vditor'
import 'vditor/dist/index.css'

const app = createApp(App)
app.config.globalProperties.Vditor = Vditor
app.provide('Vditor', Vditor)
app.use(router)
app.use(ElementPlus)
app.mount('#app')