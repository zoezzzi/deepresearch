export interface CreateResearchRequest {
  topic: string
  description?: string
}

export interface Task {
  taskId: string
  title: string
  intent: string
  query: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  summary?: string
  sourcesSummary?: string
  notices?: string
  startedAt?: string
  completedAt?: string
}

export type WorkflowStatus = 'pending' | 'running' | 'all_success' | 'partial_failed' | 'all_failed' | 'report_failed'

export interface ResearchWorkflow {
  workflowId: string
  topic: string
  description?: string
  status: WorkflowStatus
  tasks: Task[]
  reportUrl?: string
  reportContent?: string
  createdAt: string
  updatedAt: string
}

export type SSEEventType = 'plan' | 'task_start' | 'task_complete' | 'chunk' | 'result' | 'error'

export interface SSEEvent {
  type: SSEEventType
  data: any
}

export function mapWorkflowStatusToDisplay(status: WorkflowStatus): 'pending' | 'running' | 'completed' | 'failed' {
  if (status === 'all_success' || status === 'partial_failed') {
    return 'completed'
  }
  if (status === 'all_failed' || status === 'report_failed') {
    return 'failed'
  }
  return status
}
