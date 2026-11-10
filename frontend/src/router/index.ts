import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

/**
 * 应用路由表：三个页面分别对应创建调研、任务进度、报告预览。
 * 详情页与报告页通过 workflowId 路由参数关联同一份工作流。
 */
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
