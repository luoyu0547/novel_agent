import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: AppLayout,
      redirect: '/novels',
      children: [
        { path: 'novels', name: 'novels', component: () => import('@/views/novels/NovelListView.vue'), meta: { auth: true } },
        { path: 'novels/:id', name: 'novel-detail', component: () => import('@/views/novels/NovelDetailView.vue'), meta: { auth: true } },
        { path: 'novels/:id/characters', name: 'novel-characters', component: () => import('@/views/novels/CharacterListView.vue'), meta: { auth: true } },
        { path: 'novels/:id/settings', name: 'novel-settings', component: () => import('@/views/novels/WorldSettingsView.vue'), meta: { auth: true } },
        { path: 'novels/:id/pending', name: 'novel-pending', component: () => import('@/views/novels/PendingConfirmView.vue'), meta: { auth: true } },
        { path: 'novels/:id/writing', name: 'writing-workspace', component: () => import('@/views/novels/WritingWorkspaceView.vue'), meta: { auth: true } },
      ],
    },
    { path: '/novels/:id/edit/:chapterId', name: 'editor', component: () => import('@/views/editor/EditorView.vue'), meta: { auth: true } },
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { guest: true } },
    { path: '/register', name: 'register', component: () => import('@/views/auth/RegisterView.vue'), meta: { guest: true } },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.auth && !token) next('/login')
  else if (to.meta.guest && token) next('/novels')
  else next()
})

export default router
