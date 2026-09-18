import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

import Home from './views/Home.vue'
import Play from './views/Play.vue'
import LocalPlay from './views/LocalPlay.vue'
import Review from './views/Review.vue'
import Admin from './views/Admin.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/play/:date', component: Play, props: true },
  { path: '/local', component: LocalPlay },
  { path: '/review', component: Review },
  { path: '/admin', component: Admin },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.mount('#app')
