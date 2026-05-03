<template>
  <div class="task-card" :class="statusClass">
    <div class="task-header">
      <div class="task-icon">{{ statusIcon }}</div>
      <div class="task-status" :class="statusClass">{{ statusText }}</div>
    </div>
    <h3 class="task-title">{{ task.title }}</h3>
    <p class="task-intent">{{ task.intent }}</p>
    <p class="task-query">查询: {{ task.query }}</p>
    
    <div v-if="task.summary" class="task-results">
      <div class="result-section">
        <h4>总结</h4>
        <p>{{ task.summary }}</p>
      </div>
      <div v-if="task.sourcesSummary" class="result-section">
        <h4>来源</h4>
        <p>{{ task.sourcesSummary }}</p>
      </div>
      <div v-if="task.notices" class="result-section notice">
        <h4>注意事项</h4>
        <p>{{ task.notices }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@/types'

interface Props {
  task: Task
}

const props = defineProps<Props>()

const statusClass = computed(() => {
  if (props.task.status === 'completed') return 'success'
  if (props.task.status === 'failed') return 'error'
  if (props.task.status === 'running') return 'running'
  if (props.task.status === 'skipped') return 'skipped'
  return 'pending'
})

const statusText = computed(() => {
  if (props.task.status === 'completed') return '已完成'
  if (props.task.status === 'failed') return '失败'
  if (props.task.status === 'running') return '进行中'
  if (props.task.status === 'skipped') return '跳过'
  return '等待中'
})

const statusIcon = computed(() => {
  if (props.task.status === 'completed') return '✓'
  if (props.task.status === 'failed') return '✗'
  if (props.task.status === 'running') return '⚡'
  if (props.task.status === 'skipped') return '⊘'
  return '○'
})
</script>

<style scoped>
.task-card {
  background: #f7fafc;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  padding: 1.25rem;
  transition: all 0.2s;
}

.task-card.pending {
  opacity: 0.7;
}

.task-card.running {
  border-color: #4299e1;
  background: linear-gradient(135deg, #ebf8ff 0%, #e6fffa 100%);
  animation: pulse 2s infinite;
}

.task-card.success {
  border-color: #48bb78;
  background: #f0fff4;
}

.task-card.error {
  border-color: #fc8181;
  background: #fff5f5;
}

.task-card.skipped {
  border-color: #cbd5e0;
  background: #f7fafc;
  opacity: 0.5;
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(66, 153, 225, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(66, 153, 225, 0);
  }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.task-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 1rem;
  font-weight: 700;
}

.task-card.pending .task-icon {
  background: #e2e8f0;
  color: #718096;
}

.task-card.running .task-icon {
  background: #4299e1;
  color: white;
}

.task-card.success .task-icon {
  background: #48bb78;
  color: white;
}

.task-card.error .task-icon {
  background: #fc8181;
  color: white;
}

.task-card.skipped .task-icon {
  background: #cbd5e0;
  color: #718096;
}

.task-status {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
}

.task-status.pending {
  background: #e2e8f0;
  color: #718096;
}

.task-status.running {
  background: #bee3f8;
  color: #2b6cb0;
}

.task-status.success {
  background: #c6f6d5;
  color: #276749;
}

.task-status.error {
  background: #fed7d7;
  color: #c53030;
}

.task-status.skipped {
  background: #e2e8f0;
  color: #718096;
}

.task-title {
  font-size: 1rem;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 0.5rem;
}

.task-intent {
  font-size: 0.875rem;
  color: #4a5568;
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

.task-query {
  font-size: 0.8125rem;
  color: #718096;
  font-family: 'Fira Code', monospace;
  background: white;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.task-results {
  border-top: 1px solid #e2e8f0;
  padding-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.result-section h4 {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 0.25rem;
}

.result-section p {
  font-size: 0.8125rem;
  color: #4a5568;
  line-height: 1.5;
}

.result-section.notice {
  background: #fffaf0;
  padding: 0.75rem;
  border-radius: 6px;
  border-left: 3px solid #ed8936;
}
</style>
