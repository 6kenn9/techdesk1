import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { makeRouter } from './router'
import './style.css'
import './flow.css'
import './theme'

const pinia = createPinia()
createApp(App).use(pinia).use(makeRouter(pinia)).mount('#app')
