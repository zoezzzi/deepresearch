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

export interface ResearchWorkflow {
  workflowId: string
  topic: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
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
