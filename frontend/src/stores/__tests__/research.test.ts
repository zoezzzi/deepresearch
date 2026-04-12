import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useResearchStore } from '@/stores/research'
import { researchApi } from '@/api/client'
import { sseClient } from '@/api/sse'
import type { ResearchWorkflow, Task } from '@/types'

vi.mock('@/api/client')
vi.mock('@/api/sse')

describe('ResearchStore - 轮询机制', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  describe('startPolling', () => {
    it('应该在任务状态变化时更新工作流', async () => {
      const store = useResearchStore()
      
      const initialWorkflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [
          {
            taskId: 'task-1',
            title: '任务1',
            intent: '研究意图',
            query: '搜索查询',
            status: 'pending',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      const updatedWorkflow: ResearchWorkflow = {
        ...initialWorkflow,
        tasks: [
          {
            ...initialWorkflow.tasks[0],
            status: 'completed',
            summary: '任务完成摘要',
            sourcesSummary: '来源摘要',
            notices: '注意事项'
          }
        ]
      }
      
      vi.mocked(researchApi.getWorkflow)
        .mockResolvedValueOnce(initialWorkflow)
        .mockResolvedValueOnce(updatedWorkflow)
      
      await store.fetchWorkflow('test-workflow-id')
      expect(store.currentWorkflow?.tasks[0].status).toBe('pending')
      
      store.startPolling('test-workflow-id')
      
      await vi.advanceTimersByTimeAsync(3000)
      
      expect(store.currentWorkflow?.tasks[0].status).toBe('completed')
      expect(store.currentWorkflow?.tasks[0].summary).toBe('任务完成摘要')
      expect(store.currentWorkflow?.tasks[0].sourcesSummary).toBe('来源摘要')
      expect(store.currentWorkflow?.tasks[0].notices).toBe('注意事项')
    })

    it('应该在任务数量变化时更新工作流', async () => {
      const store = useResearchStore()
      
      const initialWorkflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [
          {
            taskId: 'task-1',
            title: '任务1',
            intent: '研究意图',
            query: '搜索查询',
            status: 'pending',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      const updatedWorkflow: ResearchWorkflow = {
        ...initialWorkflow,
        tasks: [
          initialWorkflow.tasks[0],
          {
            taskId: 'task-2',
            title: '任务2',
            intent: '研究意图2',
            query: '搜索查询2',
            status: 'pending',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ]
      }
      
      vi.mocked(researchApi.getWorkflow)
        .mockResolvedValueOnce(initialWorkflow)
        .mockResolvedValueOnce(updatedWorkflow)
      
      await store.fetchWorkflow('test-workflow-id')
      expect(store.tasks.length).toBe(1)
      
      store.startPolling('test-workflow-id')
      
      await vi.advanceTimersByTimeAsync(3000)
      
      expect(store.tasks.length).toBe(2)
    })

    it('应该在工作流状态变化时更新', async () => {
      const store = useResearchStore()
      
      const initialWorkflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      const completedWorkflow: ResearchWorkflow = {
        ...initialWorkflow,
        status: 'completed',
        reportUrl: '/reports/test-report.md'
      }
      
      vi.mocked(researchApi.getWorkflow)
        .mockResolvedValueOnce(initialWorkflow)
        .mockResolvedValueOnce(completedWorkflow)
      
      await store.fetchWorkflow('test-workflow-id')
      expect(store.currentWorkflow?.status).toBe('running')
      
      store.startPolling('test-workflow-id')
      
      await vi.advanceTimersByTimeAsync(3000)
      
      expect(store.currentWorkflow?.status).toBe('completed')
      expect(store.currentWorkflow?.reportUrl).toBe('/reports/test-report.md')
    })

    it('应该在任务状态相同时不更新', async () => {
      const store = useResearchStore()
      
      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [
          {
            taskId: 'task-1',
            title: '任务1',
            intent: '研究意图',
            query: '搜索查询',
            status: 'pending',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow)
        .mockResolvedValueOnce(workflow)
        .mockResolvedValueOnce(workflow)
      
      await store.fetchWorkflow('test-workflow-id')
      
      store.startPolling('test-workflow-id')
      
      await vi.advanceTimersByTimeAsync(3000)
      
      expect(researchApi.getWorkflow).toHaveBeenCalledTimes(2)
    })
  })
})

describe('ResearchStore - SSE 事件处理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('task_start 事件', () => {
    it('应该处理 task_start 事件（使用 task_id 字段）', async () => {
      const store = useResearchStore()
      
      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [
          {
            taskId: 'task-1',
            title: '任务1',
            intent: '研究意图',
            query: '搜索查询',
            status: 'pending',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow).mockResolvedValueOnce(workflow)
      vi.mocked(sseClient.connect).mockImplementation(() => {})
      vi.mocked(sseClient.on).mockImplementation(() => {})
      
      await store.fetchWorkflow('test-workflow-id')
      store.connectSSE('test-workflow-id')
      
      const taskStartHandler = vi.mocked(sseClient.on).mock.calls.find(
        call => call[0] === 'task_start'
      )?.[1]
      
      if (taskStartHandler) {
        taskStartHandler({
          type: 'task_start',
          data: {
            task_id: 'task-1',
            task_title: '任务1'
          }
        })
        
        expect(store.tasks[0].status).toBe('running')
      }
    })

    it('应该处理 task_start 事件（使用 taskId 字段）', async () => {
      const store = useResearchStore()
      
      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [
          {
            taskId: 'task-1',
            title: '任务1',
            intent: '研究意图',
            query: '搜索查询',
            status: 'pending',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow).mockResolvedValueOnce(workflow)
      vi.mocked(sseClient.connect).mockImplementation(() => {})
      vi.mocked(sseClient.on).mockImplementation(() => {})
      
      await store.fetchWorkflow('test-workflow-id')
      store.connectSSE('test-workflow-id')
      
      const taskStartHandler = vi.mocked(sseClient.on).mock.calls.find(
        call => call[0] === 'task_start'
      )?.[1]
      
      if (taskStartHandler) {
        taskStartHandler({
          type: 'task_start',
          data: {
            taskId: 'task-1',
            task_title: '任务1'
          }
        })
        
        expect(store.tasks[0].status).toBe('running')
      }
    })
  })

  describe('task_complete 事件', () => {
    it('应该处理 task_complete 事件并更新所有字段', async () => {
      const store = useResearchStore()
      
      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [
          {
            taskId: 'task-1',
            title: '任务1',
            intent: '研究意图',
            query: '搜索查询',
            status: 'running',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow).mockResolvedValueOnce(workflow)
      vi.mocked(sseClient.connect).mockImplementation(() => {})
      vi.mocked(sseClient.on).mockImplementation(() => {})
      
      await store.fetchWorkflow('test-workflow-id')
      store.connectSSE('test-workflow-id')
      
      const taskCompleteHandler = vi.mocked(sseClient.on).mock.calls.find(
        call => call[0] === 'task_complete'
      )?.[1]
      
      if (taskCompleteHandler) {
        taskCompleteHandler({
          type: 'task_complete',
          data: {
            task_id: 'task-1',
            task_title: '任务1',
            summary: '任务完成摘要',
            sources_summary: '来源摘要',
            notices: '注意事项'
          }
        })
        
        expect(store.tasks[0].status).toBe('completed')
        expect(store.tasks[0].summary).toBe('任务完成摘要')
        expect(store.tasks[0].sourcesSummary).toBe('来源摘要')
        expect(store.tasks[0].notices).toBe('注意事项')
      }
    })

    it('应该兼容 sourcesSummary 和 sources_summary 字段', async () => {
      const store = useResearchStore()
      
      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [
          {
            taskId: 'task-1',
            title: '任务1',
            intent: '研究意图',
            query: '搜索查询',
            status: 'running',
            summary: null,
            sourcesSummary: null,
            notices: null,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z'
          }
        ],
        reportUrl: null,
        reportContent: null,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow).mockResolvedValueOnce(workflow)
      vi.mocked(sseClient.connect).mockImplementation(() => {})
      vi.mocked(sseClient.on).mockImplementation(() => {})
      
      await store.fetchWorkflow('test-workflow-id')
      store.connectSSE('test-workflow-id')
      
      const taskCompleteHandler = vi.mocked(sseClient.on).mock.calls.find(
        call => call[0] === 'task_complete'
      )?.[1]
      
      if (taskCompleteHandler) {
        taskCompleteHandler({
          type: 'task_complete',
          data: {
            task_id: 'task-1',
            task_title: '任务1',
            summary: '任务完成摘要',
            sourcesSummary: '来源摘要（camelCase）',
            notices: '注意事项'
          }
        })
        
        expect(store.tasks[0].sourcesSummary).toBe('来源摘要（camelCase）')
      }
    })
  })
})
