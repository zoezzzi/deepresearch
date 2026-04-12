import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ResearchWorkflow, Task } from '@/types'
import { researchApi } from '@/api/client'
import { sseClient } from '@/api/sse'

export const useResearchStore = defineStore('research', () => {
  const currentWorkflow = ref<ResearchWorkflow | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const pollingInterval = ref<number | null>(null)

  const currentWorkflowId = computed(() => currentWorkflow.value?.workflowId)
  const currentStatus = computed(() => currentWorkflow.value?.status)
  const tasks = computed(() => currentWorkflow.value?.tasks || [])
  const reportContent = computed(() => currentWorkflow.value?.reportContent || '')

  function startPolling(workflowId: string): void {
    if (pollingInterval.value) return
    
    pollingInterval.value = window.setInterval(async () => {
      try {
        const workflow = await researchApi.getWorkflow(workflowId)
        const currentTasks = currentWorkflow.value?.tasks || []
        let shouldUpdate = false
        
        // 检查工作流状态是否变化
        if (currentWorkflow.value && workflow.status !== currentWorkflow.value.status) {
          shouldUpdate = true
        }
        
        // 检查报告 URL 是否出现
        const hasNewReport = workflow.reportUrl && !currentWorkflow.value?.reportUrl
        
        // 检查任务数量或状态是否有变化
        if (workflow.tasks && workflow.tasks.length > 0) {
          if (workflow.tasks.length !== currentTasks.length) {
            shouldUpdate = true
          } else {
            // 检查每个任务的状态是否变化
            for (let i = 0; i < workflow.tasks.length; i++) {
              const newTask = workflow.tasks[i]
              const oldTask = currentTasks[i]
              if (newTask.status !== oldTask.status || 
                  newTask.summary !== oldTask.summary ||
                  newTask.sourcesSummary !== oldTask.sourcesSummary ||
                  newTask.notices !== oldTask.notices) {
                shouldUpdate = true
                break
              }
            }
          }
        }
        
        if (shouldUpdate || hasNewReport) {
          console.log(`[Polling] Workflow updated, refreshing data`)
          currentWorkflow.value = workflow
          
          // 如果有新的报告 URL，加载报告内容
          if (hasNewReport) {
            await fetchReportContent(workflowId)
          }
        }
      } catch (err) {
        console.error('[Polling] Failed to fetch workflow:', err)
      }
    }, 3000) // 每 3 秒轮询一次
    console.log(`[ResearchStore] Started polling for workflow ${workflowId}`)
  }

  function stopPolling(): void {
    if (pollingInterval.value) {
      window.clearInterval(pollingInterval.value)
      pollingInterval.value = null
      console.log('[ResearchStore] Stopped polling')
    }
  }

  async function createResearch(topic: string, description?: string): Promise<string> {
    isLoading.value = true
    error.value = null

    try {
      const response = await researchApi.createResearch({ topic, description })
      await fetchWorkflow(response.workflowId)
      connectSSE(response.workflowId)
      return response.workflowId
    } catch (err) {
      error.value = err instanceof Error ? err.message : '创建调研失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchWorkflow(workflowId: string): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const workflow = await researchApi.getWorkflow(workflowId)
      currentWorkflow.value = workflow
      
      // 如果有任务，立即更新
      if (workflow.tasks && workflow.tasks.length > 0) {
        console.log(`[ResearchStore] Fetched ${workflow.tasks.length} tasks from backend for workflow ${workflowId}`)
      } else {
        console.log(`[ResearchStore] No tasks found for workflow ${workflowId}, waiting for plan event...`)
      }
      
      // 如果有报告 URL，加载报告内容
      if (workflow.reportUrl) {
        await fetchReportContent(workflowId)
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取工作流失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }
  
  async function fetchReportContent(workflowId: string): Promise<void> {
    if (!currentWorkflow.value?.reportUrl) return
    
    try {
      const content = await researchApi.getReportContent(workflowId)
      if (currentWorkflow.value) {
        currentWorkflow.value.reportContent = content
      }
    } catch (err) {
      console.error('[ResearchStore] Failed to fetch report content:', err)
    }
  }

  function connectSSE(workflowId: string): void {
    sseClient.connect(workflowId)

    sseClient.on('plan', (event) => {
      console.log('[SSE] Received plan event with', event.data.tasks?.length || 0, 'tasks')
      if (currentWorkflow.value) {
        currentWorkflow.value.tasks = event.data.tasks
        // 收到 plan 事件后停止轮询
        stopPolling()
      }
    })

    sseClient.on('task_start', (event) => {
      const taskId = event.data.taskId || event.data.task_id
      updateTask(taskId, { status: 'running', startedAt: new Date().toISOString() })
    })

    sseClient.on('task_complete', (event) => {
      const taskId = event.data.taskId || event.data.task_id
      updateTask(taskId, {
        status: 'completed',
        summary: event.data.summary,
        sourcesSummary: event.data.sourcesSummary || event.data.sources_summary,
        notices: event.data.notices,
        completedAt: new Date().toISOString()
      })
    })

    sseClient.on('chunk', (event) => {
      if (currentWorkflow.value) {
        currentWorkflow.value.reportContent = (currentWorkflow.value.reportContent || '') + event.data.content
      }
    })

    sseClient.on('result', async (event) => {
      if (currentWorkflow.value) {
        currentWorkflow.value.status = 'all_success'
        currentWorkflow.value.reportUrl = event.data.reportUrl
        // 收到 result 事件后，加载报告内容
        await fetchReportContent(workflowId)
      }
      stopPolling()
      sseClient.disconnect()
    })

    sseClient.on('error', (event) => {
      if (currentWorkflow.value) {
        currentWorkflow.value.status = 'all_failed'
      }
      error.value = event.data.message
      stopPolling()
      sseClient.disconnect()
    })

    // 启动轮询作为备用方案
    startPolling(workflowId)
  }

  function updateTask(taskId: string, updates: Partial<Task>): void {
    if (!currentWorkflow.value) return

    const taskIndex = currentWorkflow.value.tasks.findIndex(task => task.taskId === taskId)
    if (taskIndex !== -1) {
      currentWorkflow.value.tasks[taskIndex] = {
        ...currentWorkflow.value.tasks[taskIndex],
        ...updates
      }
    }
  }

  function disconnectSSE(): void {
    sseClient.disconnect()
    stopPolling()
  }

  function reset(): void {
    disconnectSSE()
    currentWorkflow.value = null
    error.value = null
  }

  return {
    currentWorkflow,
    isLoading,
    error,
    currentWorkflowId,
    currentStatus,
    tasks,
    reportContent,
    createResearch,
    fetchWorkflow,
    fetchReportContent,
    connectSSE,
    disconnectSSE,
    reset,
    startPolling,
    stopPolling
  }
})
