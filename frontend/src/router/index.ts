import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/ResearchForm.vue')
  },
  {
    path: '/research/:workflowId',
    name: 'ResearchDetail',
    component: () => import('@/views/TaskBoard.vue')
  },
  {
    path: '/report/:workflowId',
    name: 'ReportPreview',
    component: () => import('@/views/ReportPreview.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
