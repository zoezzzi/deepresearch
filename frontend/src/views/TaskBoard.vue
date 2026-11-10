<template>
  <div class="task-board-container">
    <div class="header-section">
      <div>
        <h1 class="workflow-title">{{ workflow?.topic }}</h1>
        <p v-if="workflow?.description" class="workflow-description">
          {{ workflow.description }}
        </p>
      </div>
      <div class="status-badge" :class="statusClass">
        {{ statusText }}
      </div>
    </div>

    <div v-if="error" class="error-alert">
      <span>{{ error }}</span>
      <button type="button" class="retry-button" @click="reload">重试</button>
    </div>

    <div v-if="isLoading && !workflow" class="loading-container">
      <div class="spinner-large"></div>
      <p>加载中...</p>
    </div>

    <div v-else class="content-section">
      <div class="tasks-section">
        <h2 class="section-title">任务列表</h2>
        <div v-if="tasks.length === 0" class="empty-state">
          <div class="empty-icon">📋</div>
          <p>正在生成调研计划...</p>
        </div>
        <div v-else class="tasks-list">
          <TaskCard v-for="task in tasks" :key="task.taskId" :task="task" />
        </div>
      </div>

      <div class="report-preview-section">
        <div class="report-header">
          <h2 class="section-title">报告预览</h2>
          <router-link
            v-if="canViewFullReport"
            :to="`/report/${workflowId}`"
            class="view-full-report"
          >
            查看完整报告 →
          </router-link>
        </div>
        <div v-if="!reportContent" class="empty-report">
          <div class="empty-icon">📝</div>
          <p>报告将在任务完成后生成</p>
        </div>
        <div v-else class="report-content">
          <div class="markdown-preview" v-html="renderedMarkdown"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { useResearchStore } from '@/stores/research'
import { mapWorkflowStatusToDisplay } from '@/types'
import TaskCard from '@/components/TaskCard.vue'

const route = useRoute()
const researchStore = useResearchStore()
const workflowId = route.params.workflowId as string

const workflow = computed(() => researchStore.currentWorkflow)
const tasks = computed(() => researchStore.tasks)
const reportContent = computed(() => researchStore.reportContent)
const isLoading = computed(() => researchStore.isLoading)
const error = computed(() => researchStore.error)

const renderedMarkdown = computed(() => {
  try {
    return marked(reportContent.value || '') as string
  } catch (err) {
    console.error('[TaskBoard] 报告渲染失败:', err)
    return '<p>报告渲染失败，请稍后重试或下载原文查看</p>'
  }
})

const statusClass = computed(() => {
  const status = workflow.value?.status
  if (!status) return 'pending'
  const displayStatus = mapWorkflowStatusToDisplay(status)
  if (displayStatus === 'completed') return 'success'
  if (displayStatus === 'failed') return 'error'
  if (displayStatus === 'running') return 'running'
  return 'pending'
})

const statusText = computed(() => {
  const status = workflow.value?.status
  if (!status) return '等待中'
  const displayStatus = mapWorkflowStatusToDisplay(status)
  if (displayStatus === 'completed') return '已完成'
  if (displayStatus === 'failed') return '失败'
  if (displayStatus === 'running') return '运行中'
  return '等待中'
})

const canViewFullReport = computed(() => {
  const status = workflow.value?.status
  if (!status) return false
  const displayStatus = mapWorkflowStatusToDisplay(status)
  return displayStatus === 'completed'
})

async function loadWorkflow() {
  if (!workflowId) return

  try {
    if (!researchStore.currentWorkflow || researchStore.currentWorkflow.workflowId !== workflowId) {
      await researchStore.fetchWorkflow(workflowId)
    }

    // 无论快照是否已在 store 中，都要确保 SSE/轮询通道开启，
    // 否则从其他页面返回时任务列表会停留在离开前的旧状态
    researchStore.connectSSE(workflowId)

    if (researchStore.currentWorkflow?.reportUrl && !researchStore.reportContent) {
      // 如果工作流已加载，有报告 URL 但没有报告内容，加载报告内容
      await researchStore.fetchReportContent(workflowId)
    }
  } catch (err) {
    // store 已写入可展示的错误信息，这里只避免未处理的 Promise 拒绝
    console.error('[TaskBoard] 加载工作流失败:', err)
  }
}

/** 重试：断开可能已失效的实时通道后重新拉取快照 */
function reload() {
  researchStore.disconnectSSE()
  loadWorkflow()
}

onMounted(loadWorkflow)

onUnmounted(() => {
  researchStore.disconnectSSE()
})
</script>

<style scoped>
.task-board-container {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.header-section {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
}

.workflow-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1a202c;
  margin-bottom: 0.5rem;
}

.workflow-description {
  color: #718096;
  line-height: 1.6;
}

.status-badge {
  padding: 0.5rem 1.25rem;
  border-radius: 20px;
  font-weight: 600;
  font-size: 0.875rem;
  white-space: nowrap;
}

.status-badge.pending {
  background-color: #edf2f7;
  color: #4a5568;
}

.status-badge.running {
  background-color: #ebf8ff;
  color: #2b6cb0;
}

.status-badge.success {
  background-color: #f0fff4;
  color: #276749;
}

.status-badge.error {
  background-color: #fff5f5;
  color: #c53030;
}

.error-alert {
  padding: 1rem 1.5rem;
  background-color: #fff5f5;
  border: 1px solid #fc8181;
  border-radius: 8px;
  color: #c53030;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.retry-button {
  padding: 0.4rem 1rem;
  border: 1px solid #c53030;
  border-radius: 6px;
  background: white;
  color: #c53030;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.retry-button:hover {
  background: #fff5f5;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  gap: 1rem;
  color: #718096;
}

.spinner-large {
  width: 50px;
  height: 50px;
  border: 4px solid #e2e8f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.content-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
}

.tasks-section,
.report-preview-section {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #2d3748;
  margin-bottom: 1.5rem;
}

.report-header .section-title {
  margin-bottom: 0;
}

.view-full-report {
  color: #667eea;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9375rem;
}

.view-full-report:hover {
  text-decoration: underline;
}

.empty-state,
.empty-report {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  gap: 1rem;
  color: #718096;
}

.empty-icon {
  font-size: 3rem;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 600px;
  overflow-y: auto;
}

.report-content {
  max-height: 600px;
  overflow-y: auto;
}

.markdown-preview {
  line-height: 1.8;
  color: #2d3748;
}

.markdown-preview :deep(h1),
.markdown-preview :deep(h2),
.markdown-preview :deep(h3) {
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  font-weight: 700;
}

.markdown-preview :deep(h1) {
  font-size: 1.75rem;
}

.markdown-preview :deep(h2) {
  font-size: 1.5rem;
}

.markdown-preview :deep(h3) {
  font-size: 1.25rem;
}

.markdown-preview :deep(p) {
  margin-bottom: 1rem;
}

.markdown-preview :deep(ul),
.markdown-preview :deep(ol) {
  margin-left: 1.5rem;
  margin-bottom: 1rem;
}

.markdown-preview :deep(code) {
  background-color: #f7fafc;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 0.9em;
}

.markdown-preview :deep(pre) {
  background-color: #2d3748;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 1rem;
}

.markdown-preview :deep(pre code) {
  background: none;
  padding: 0;
}

@media (max-width: 968px) {
  .content-section {
    grid-template-columns: 1fr;
  }
}
</style>
