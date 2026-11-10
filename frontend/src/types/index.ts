export interface CreateResearchRequest {
  topic: string
  description?: string
}

export interface ScenarioUIConfig {
  navbarTitle?: string
  formTitle?: string
  topicLabel?: string
  topicPlaceholder?: string
}

export interface ScenarioMetadata {
  scenarioId: string
  name: string
  description: string
  version: string
  author?: string
  uiConfig?: ScenarioUIConfig
}

export interface Task {
  taskId: string
  title: string
  intent: string
  query: string
  order: number
  dependsOn: string[]
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  summary?: string | null
  sourcesSummary?: string | null
  notices?: string | null
  createdAt?: string
  updatedAt?: string
  startedAt?: string
  completedAt?: string
}

export type WorkflowStatus =
  'pending' | 'running' | 'all_success' | 'partial_failed' | 'all_failed' | 'report_failed'

export interface ResearchWorkflow {
  workflowId: string
  topic: string
  description?: string
  status: WorkflowStatus
  tasks: Task[]
  // 后端未生成报告时返回 null，类型上显式允许，避免上层强转
  reportUrl?: string | null
  reportContent?: string | null
  createdAt: string
  updatedAt: string
}

export type SSEEventType = 'plan' | 'task_start' | 'task_complete' | 'chunk' | 'result' | 'error'

export interface SSEEvent {
  type: SSEEventType
  data: any
}

export function mapWorkflowStatusToDisplay(
  status: WorkflowStatus | string
): 'pending' | 'running' | 'completed' | 'failed' {
  if (status === 'all_success' || status === 'partial_failed') {
    return 'completed'
  }
  if (status === 'all_failed' || status === 'report_failed') {
    return 'failed'
  }
  if (status === 'pending' || status === 'running') {
    return status
  }
  // 后端新增状态时按等待中处理，避免页面整块渲染为空白
  return 'pending'
}
