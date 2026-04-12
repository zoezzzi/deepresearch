import axios from 'axios'
import type { CreateResearchRequest, ResearchWorkflow, Task } from '@/types'

const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

function transformTaskFromBackend(task: any): Task {
  return {
    taskId: task.task_id,
    title: task.title,
    intent: task.intent,
    query: task.query,
    status: task.status,
    summary: task.summary,
    sourcesSummary: task.sources_summary,
    notices: task.notices,
    createdAt: task.created_at,
    updatedAt: task.updated_at,
    startedAt: task.started_at,
    completedAt: task.completed_at
  }
}

function transformWorkflowFromBackend(data: any): ResearchWorkflow {
  return {
    workflowId: data.workflow_id,
    topic: data.topic,
    description: data.description,
    status: data.status,
    tasks: (data.tasks || []).map(transformTaskFromBackend),
    reportUrl: data.report_url,
    reportContent: data.report_content,
    createdAt: data.created_at,
    updatedAt: data.updated_at
  }
}

export const researchApi = {
  createResearch: async (request: CreateResearchRequest): Promise<{ workflowId: string }> => {
    const response = await apiClient.post('/research', request)
    return { workflowId: response.data.workflow_id }
  },

  getWorkflow: async (workflowId: string): Promise<ResearchWorkflow> => {
    const response = await apiClient.get(`/research/${workflowId}`)
    return transformWorkflowFromBackend(response.data)
  },

  getReportContent: async (workflowId: string): Promise<string> => {
    const response = await apiClient.get(`/research/${workflowId}/report-content`)
    return response.data.content
  }
}

export default apiClient
