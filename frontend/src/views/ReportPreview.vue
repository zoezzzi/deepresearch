<template>
  <div class="report-preview-container">
    <div class="header-section">
      <div class="header-content">
        <router-link to="/" class="back-link">← 返回首页</router-link>
        <h1 class="report-title">{{ workflow?.topic }}</h1>
        <p v-if="workflow?.description" class="report-description">
          {{ workflow.description }}
        </p>
      </div>
      <div class="header-actions">
        <button v-if="workflow?.reportUrl" class="download-button" @click="downloadReport">
          下载报告
        </button>
      </div>
    </div>

    <div v-if="error" class="error-alert">
      {{ error }}
    </div>

    <div v-if="isLoading" class="loading-container">
      <div class="spinner-large"></div>
      <p>加载报告...</p>
    </div>

    <div v-else-if="!reportContent" class="empty-state">
      <div class="empty-icon">📄</div>
      <h2>报告尚未生成</h2>
      <p>请等待调研任务完成后再查看报告</p>
      <router-link :to="`/research/${workflowId}`" class="view-progress-link">
        查看任务进度 →
      </router-link>
    </div>

    <div v-else class="report-content">
      <div class="markdown-body" v-html="renderedMarkdown"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { useResearchStore } from '@/stores/research'

const route = useRoute()
const researchStore = useResearchStore()
const workflowId = route.params.workflowId as string

const workflow = computed(() => researchStore.currentWorkflow)
const reportContent = computed(() => researchStore.reportContent)
const isLoading = computed(() => researchStore.isLoading)
const error = computed(() => researchStore.error)

const renderedMarkdown = computed(() => {
  return marked(reportContent.value || '')
})

function downloadReport() {
  if (workflow.value?.reportUrl) {
    window.open(workflow.value.reportUrl, '_blank')
  }
}

onMounted(async () => {
  if (workflowId) {
    if (!researchStore.currentWorkflow || researchStore.currentWorkflow.workflowId !== workflowId) {
      await researchStore.fetchWorkflow(workflowId)
    }
  }
})
</script>

<style scoped>
.report-preview-container {
  max-width: 900px;
  margin: 0 auto;
}

.header-section {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 2rem;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 2rem;
}

.header-content {
  flex: 1;
}

.back-link {
  display: inline-block;
  color: #667eea;
  text-decoration: none;
  font-size: 0.9375rem;
  font-weight: 500;
  margin-bottom: 1rem;
}

.back-link:hover {
  text-decoration: underline;
}

.report-title {
  font-size: 2rem;
  font-weight: 700;
  color: #1a202c;
  margin-bottom: 0.75rem;
}

.report-description {
  color: #718096;
  font-size: 1.125rem;
  line-height: 1.6;
}

.download-button {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  white-space: nowrap;
}

.download-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.error-alert {
  padding: 1rem 1.5rem;
  background-color: #fff5f5;
  border: 1px solid #fc8181;
  border-radius: 8px;
  color: #c53030;
  margin-bottom: 2rem;
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

.empty-state {
  background: white;
  padding: 4rem 2rem;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.empty-icon {
  font-size: 4rem;
}

.empty-state h2 {
  font-size: 1.5rem;
  font-weight: 700;
  color: #2d3748;
}

.empty-state p {
  color: #718096;
  font-size: 1rem;
}

.view-progress-link {
  margin-top: 1rem;
  display: inline-block;
  padding: 0.75rem 1.5rem;
  background: #667eea;
  color: white;
  text-decoration: none;
  border-radius: 8px;
  font-weight: 600;
  transition: background 0.2s;
}

.view-progress-link:hover {
  background: #5a67d8;
}

.report-content {
  background: white;
  padding: 3rem;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.markdown-body {
  line-height: 1.8;
  color: #2d3748;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin-top: 2rem;
  margin-bottom: 1rem;
  font-weight: 700;
  line-height: 1.3;
}

.markdown-body :deep(h1) {
  font-size: 2.25rem;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 0.5rem;
}

.markdown-body :deep(h2) {
  font-size: 1.75rem;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.25rem;
}

.markdown-body :deep(h3) {
  font-size: 1.5rem;
}

.markdown-body :deep(h4) {
  font-size: 1.25rem;
}

.markdown-body :deep(p) {
  margin-bottom: 1.25rem;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-left: 1.5rem;
  margin-bottom: 1.25rem;
}

.markdown-body :deep(li) {
  margin-bottom: 0.5rem;
}

.markdown-body :deep(code) {
  background-color: #f7fafc;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.9em;
  color: #d63384;
}

.markdown-body :deep(pre) {
  background-color: #2d3748;
  color: #e2e8f0;
  padding: 1.25rem;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 1.25rem;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
  font-size: 0.875rem;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid #667eea;
  padding-left: 1rem;
  margin-left: 0;
  margin-bottom: 1.25rem;
  color: #4a5568;
  font-style: italic;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1.25rem;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.75rem;
  text-align: left;
}

.markdown-body :deep(th) {
  background-color: #f7fafc;
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: #667eea;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin-bottom: 1.25rem;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 2px solid #e2e8f0;
  margin: 2rem 0;
}

@media (max-width: 768px) {
  .header-section {
    flex-direction: column;
  }

  .report-content {
    padding: 1.5rem;
  }

  .report-title {
    font-size: 1.5rem;
  }
}
</style>
