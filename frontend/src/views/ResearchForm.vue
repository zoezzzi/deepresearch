<template>
  <div class="research-form-container">
    <div class="form-card">
      <h2 class="form-title">开始新的调研</h2>
      <p class="form-description">
        输入您感兴趣的主题，AI 将帮助您完成系统性的调研并生成完整报告
      </p>

      <form @submit.prevent="handleSubmit" class="form">
        <div class="form-group">
          <label for="topic" class="form-label">调研主题 *</label>
          <input
            id="topic"
            v-model="topic"
            type="text"
            class="form-input"
            placeholder="例如：人工智能在医疗领域的应用"
            required
          />
        </div>

        <div class="form-group">
          <label for="description" class="form-label">详细描述（可选）</label>
          <textarea
            id="description"
            v-model="description"
            class="form-textarea"
            placeholder="请描述您希望调研的方向、关注点或具体问题..."
            rows="5"
          ></textarea>
        </div>

        <button
          type="submit"
          class="submit-button"
          :disabled="isSubmitting || !topic.trim()"
        >
          <span v-if="isSubmitting" class="loading">
            <span class="spinner"></span>
            正在创建调研...
          </span>
          <span v-else>开始调研</span>
        </button>
      </form>

      <div v-if="error" class="error-message">
        {{ error }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useResearchStore } from '@/stores/research'

const router = useRouter()
const researchStore = useResearchStore()

const topic = ref('')
const description = ref('')
const isSubmitting = ref(false)
const error = ref('')

async function handleSubmit() {
  if (!topic.value.trim()) return

  isSubmitting.value = true
  error.value = ''

  try {
    const workflowId = await researchStore.createResearch(topic.value, description.value)
    router.push(`/research/${workflowId}`)
  } catch (err) {
    error.value = researchStore.error || '创建调研失败，请稍后重试'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.research-form-container {
  max-width: 700px;
  margin: 0 auto;
}

.form-card {
  background: white;
  border-radius: 12px;
  padding: 2.5rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.form-title {
  font-size: 1.875rem;
  font-weight: 700;
  color: #1a202c;
  margin-bottom: 0.5rem;
}

.form-description {
  color: #718096;
  margin-bottom: 2rem;
  line-height: 1.6;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-weight: 600;
  color: #2d3748;
  font-size: 0.9375rem;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
  font-family: inherit;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-textarea {
  resize: vertical;
}

.submit-button {
  width: 100%;
  padding: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1.125rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.submit-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.submit-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid transparent;
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.error-message {
  margin-top: 1.5rem;
  padding: 1rem;
  background-color: #fff5f5;
  border: 1px solid #fc8181;
  border-radius: 8px;
  color: #c53030;
  font-size: 0.9375rem;
}
</style>
