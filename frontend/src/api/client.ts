import axios from 'axios'
import type { CreateResearchRequest, ResearchWorkflow, Task, ScenarioMetadata } from '@/types'

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

function transformScenarioFromBackend(data: any): ScenarioMetadata {
  return {
    scenarioId: data.scenario_id,
    name: data.name,
    description: data.description,
    version: data.version,
    author: data.author,
    uiConfig: data.ui_config ? {
      navbarTitle: data.ui_config.navbar_title,
      formTitle: data.ui_config.form_title,
      topicLabel: data.ui_config.topic_label,
      topicPlaceholder: data.ui_config.topic_placeholder
    } : undefined
  }
}

export const researchApi = {
  getScenarios: async (): Promise<ScenarioMetadata[]> => {
    const response = await apiClient.get('/research/scenarios')
    return response.data.scenarios.map(transformScenarioFromBackend)
  },

  createResearch: async (request: CreateResearchRequest, scenarioId?: string): Promise<{ workflowId: string }> => {
    const params = scenarioId ? { scenario_id: scenarioId } : {}
    const response = await apiClient.post('/research', request, { params })
    return { workflowId: response.data.workflow_id }
  },

  getWorkflow: async (workflowId: string, scenarioId?: string): Promise<ResearchWorkflow> => {
    const params = scenarioId ? { scenario_id: scenarioId } : {}
    const response = await apiClient.get(`/research/${workflowId}`, { params })
    return transformWorkflowFromBackend(response.data)
  },

  getReportContent: async (workflowId: string, scenarioId?: string): Promise<string> => {
    const params = scenarioId ? { scenario_id: scenarioId } : {}
    const response = await apiClient.get(`/research/${workflowId}/report-content`, { params })
    return response.data.content
  }
}

export default apiClient
