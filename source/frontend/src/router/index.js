import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Chatbot from '../views/Chatbot.vue'
import Notes from '../views/Notes.vue'
import NotePage from '../views/NotePage.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/chatbot',
    name: 'Chatbot',
    component: Chatbot
  },
  {
    path: '/notes',
    name: 'Notes',
    component: Notes
  },
  {
    path: '/bili',
    name: 'BiliNoteQuery',
    component: NotePage,
  },
  {
    path: '/bili/:id',
    name: 'BiliNote',
    component: NotePage,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL || '/'),
  routes
})

// 若在舊路徑攜帶 bili=1 與 id，導向新樣式頁面
router.beforeEach((to, from, next) => {
  const q = to.query || {}
  const id = q.id
  const bili = q.bili
  if ((to.path === '/' || to.path === '/notes') && (bili === '1' || bili === 'true') && id) {
    next({ name: 'BiliNote', params: { id }, replace: true })
    return
  }
  next()
})

export default router 