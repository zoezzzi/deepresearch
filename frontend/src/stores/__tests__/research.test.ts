import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useResearchStore } from '@/stores/research'
import { researchApi } from '@/api/client'
import { sseClient } from '@/api/sse'
import type { ResearchWorkflow } from '@/types'

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
            order: 1,
            dependsOn: [],
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
            order: 1,
            dependsOn: [],
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
            order: 2,
            dependsOn: [],
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
        status: 'all_success',
        reportUrl: '/reports/test-report.md'
      }

      vi.mocked(researchApi.getWorkflow)
        .mockResolvedValueOnce(initialWorkflow)
        .mockResolvedValueOnce(completedWorkflow)

      await store.fetchWorkflow('test-workflow-id')
      expect(store.currentWorkflow?.status).toBe('running')

      store.startPolling('test-workflow-id')

      await vi.advanceTimersByTimeAsync(3000)

      expect(store.currentWorkflow?.status).toBe('all_success')
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
            order: 1,
            dependsOn: [],
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

describe('ResearchStore - 轮询错误处理', () => {
  const baseWorkflow: ResearchWorkflow = {
    workflowId: 'test-workflow-id',
    topic: '测试主题',
    status: 'running',
    tasks: [],
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z'
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('轮询遇到 404 时应停止轮询并展示错误', async () => {
    const store = useResearchStore()
    vi.mocked(researchApi.getWorkflow)
      .mockResolvedValueOnce(baseWorkflow)
      .mockRejectedValueOnce(
        Object.assign(new Error('工作流不存在或已被删除'), {
          code: 'WORKFLOW_NOT_FOUND',
          status: 404
        })
      )

    await store.fetchWorkflow('test-workflow-id')
    store.startPolling('test-workflow-id')
    await vi.advanceTimersByTimeAsync(3000)

    expect(store.error).toBe('工作流不存在或已被删除')
    expect(store.errorCode).toBe('WORKFLOW_NOT_FOUND')

    // 停止后不应再发起请求
    const callCount = vi.mocked(researchApi.getWorkflow).mock.calls.length
    await vi.advanceTimersByTimeAsync(60000)
    expect(researchApi.getWorkflow).toHaveBeenCalledTimes(callCount)
  })

  it('轮询失败后应退避重试，成功后清除临时错误', async () => {
    const store = useResearchStore()
    vi.mocked(researchApi.getWorkflow)
      .mockResolvedValueOnce(baseWorkflow)
      .mockRejectedValueOnce(new Error('网络错误'))
      .mockResolvedValue(baseWorkflow)

    await store.fetchWorkflow('test-workflow-id')
    store.startPolling('test-workflow-id')

    // 第一次轮询失败，进入 6 秒退避
    await vi.advanceTimersByTimeAsync(3000)
    expect(store.error).toBe('网络错误')
    expect(researchApi.getWorkflow).toHaveBeenCalledTimes(2)

    // 退避未到，不应重试
    await vi.advanceTimersByTimeAsync(3000)
    expect(researchApi.getWorkflow).toHaveBeenCalledTimes(2)

    // 达到 6 秒后重试成功，错误被清除
    await vi.advanceTimersByTimeAsync(3000)
    expect(researchApi.getWorkflow).toHaveBeenCalledTimes(3)
    expect(store.error).toBeNull()

    store.stopPolling()
  })

  it('连续失败 5 次后应停止轮询并提示刷新', async () => {
    const store = useResearchStore()
    vi.mocked(researchApi.getWorkflow)
      .mockResolvedValueOnce(baseWorkflow)
      .mockRejectedValue(new Error('网络错误'))

    await store.fetchWorkflow('test-workflow-id')
    store.startPolling('test-workflow-id')

    // 间隔依次为 3s / 6s / 12s / 24s / 30s
    await vi.advanceTimersByTimeAsync(3000)
    await vi.advanceTimersByTimeAsync(6000)
    await vi.advanceTimersByTimeAsync(12000)
    await vi.advanceTimersByTimeAsync(24000)
    await vi.advanceTimersByTimeAsync(30000)

    expect(store.error).toBe('无法获取调研进度，请稍后刷新页面重试')

    const callCount = vi.mocked(researchApi.getWorkflow).mock.calls.length
    await vi.advanceTimersByTimeAsync(60000)
    expect(researchApi.getWorkflow).toHaveBeenCalledTimes(callCount)
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
            order: 1,
            dependsOn: [],
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

      const taskStartHandler = vi
        .mocked(sseClient.on)
        .mock.calls.find((call) => call[0] === 'task_start')?.[1]

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
            order: 1,
            dependsOn: [],
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

      const taskStartHandler = vi
        .mocked(sseClient.on)
        .mock.calls.find((call) => call[0] === 'task_start')?.[1]

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
            order: 1,
            dependsOn: [],
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

      const taskCompleteHandler = vi
        .mocked(sseClient.on)
        .mock.calls.find((call) => call[0] === 'task_complete')?.[1]

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
            order: 1,
            dependsOn: [],
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

      const taskCompleteHandler = vi
        .mocked(sseClient.on)
        .mock.calls.find((call) => call[0] === 'task_complete')?.[1]

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

/** 构造测试用工作流，默认包含一个任务 */
function buildWorkflow(
  overrides: Partial<ResearchWorkflow> & { taskStatus?: ResearchWorkflow['tasks'][number]['status'] } = {}
): ResearchWorkflow {
  const { taskStatus = 'pending', ...rest } = overrides
  return {
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
        order: 1,
        dependsOn: [],
        status: taskStatus,
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
    updatedAt: '2024-01-01T00:00:00Z',
    ...rest
  }
}

describe('ResearchStore - 轮询收敛与报告重试', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.mocked(sseClient.connect).mockImplementation(() => {})
    vi.mocked(sseClient.on).mockImplementation(() => {})
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('工作流已终态但任务未完成时应继续轮询，任务完成后停止', async () => {
    const store = useResearchStore()
    const running = buildWorkflow({ status: 'running', taskStatus: 'pending' })
    const terminalPending = buildWorkflow({ status: 'all_success', taskStatus: 'pending' })
    const completed = buildWorkflow({ status: 'all_success', taskStatus: 'completed' })

    vi.mocked(researchApi.getWorkflow)
      .mockResolvedValueOnce(running)
      .mockResolvedValue(terminalPending)

    await store.fetchWorkflow('test-workflow-id')
    store.startPolling('test-workflow-id')

    await vi.advanceTimersByTimeAsync(3000)
    expect(store.currentWorkflow?.status).toBe('all_success')
    expect(store.currentWorkflow?.tasks[0].status).toBe('pending')

    // 任务仍置灰时不能停止轮询
    await vi.advanceTimersByTimeAsync(3000)
    expect(researchApi.getWorkflow).toHaveBeenCalledTimes(3)

    // 任务转为完成后，下一轮应停止轮询
    vi.mocked(researchApi.getWorkflow).mockResolvedValue(completed)
    await vi.advanceTimersByTimeAsync(3000)
    expect(store.currentWorkflow?.tasks[0].status).toBe('completed')

    const callsAfterSettled = vi.mocked(researchApi.getWorkflow).mock.calls.length
    await vi.advanceTimersByTimeAsync(60000)
    expect(researchApi.getWorkflow).toHaveBeenCalledTimes(callsAfterSettled)
  })

  it('轮询快照缺少任务时不应清空本地任务列表', async () => {
    const store = useResearchStore()
    const withTask = buildWorkflow({ status: 'running', taskStatus: 'completed' })
    const terminalWithoutTasks = buildWorkflow({
      status: 'all_success',
      taskStatus: 'completed',
      tasks: []
    })

    vi.mocked(researchApi.getWorkflow)
      .mockResolvedValueOnce(withTask)
      .mockResolvedValue(terminalWithoutTasks)

    await store.fetchWorkflow('test-workflow-id')
    store.startPolling('test-workflow-id')

    await vi.advanceTimersByTimeAsync(3000)

    expect(store.currentWorkflow?.status).toBe('all_success')
    expect(store.currentWorkflow?.tasks).toHaveLength(1)
  })

  it('result 后报告正文 404 时应退避重试直到成功', async () => {
    const store = useResearchStore()
    const running = buildWorkflow({ status: 'running', taskStatus: 'pending' })
    const completed = buildWorkflow({
      status: 'all_success',
      taskStatus: 'completed',
      reportUrl: '/reports/test-report.md'
    })

    vi.mocked(researchApi.getWorkflow)
      .mockResolvedValueOnce(running)
      .mockResolvedValue(completed)
    vi.mocked(researchApi.getReportContent)
      .mockRejectedValueOnce(new Error('Workflow or report_url not found'))
      .mockRejectedValueOnce(new Error('Workflow or report_url not found'))
      .mockResolvedValue('# 完整报告')

    await store.fetchWorkflow('test-workflow-id')
    store.connectSSE('test-workflow-id')
    // 排除轮询干扰，只验证 result 事件自身的重试
    store.stopPolling()

    const resultHandler = vi
      .mocked(sseClient.on)
      .mock.calls.find((call) => call[0] === 'result')?.[1]
    expect(resultHandler).toBeTruthy()

    const pending = resultHandler!({
      type: 'result',
      data: { reportUrl: '/reports/test-report.md' }
    })
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(2000)
    await pending

    expect(researchApi.getReportContent).toHaveBeenCalledTimes(3)
    expect(store.currentWorkflow?.reportContent).toBe('# 完整报告')
    // result 后应补拉任务快照，避免任务停留在置灰
    expect(store.currentWorkflow?.tasks[0].status).toBe('completed')
  })

  it('重复进入页面调用 connectSSE 时应恢复被停掉的轮询', async () => {
    const store = useResearchStore()
    const running = buildWorkflow({ status: 'running', taskStatus: 'pending' })
    const completed = buildWorkflow({ status: 'running', taskStatus: 'completed' })

    vi.mocked(researchApi.getWorkflow)
      .mockResolvedValueOnce(running)
      .mockResolvedValue(completed)

    await store.fetchWorkflow('test-workflow-id')
    store.connectSSE('test-workflow-id')
    // 模拟离开页面时轮询被停掉，再次进入同一工作流
    store.stopPolling()
    store.connectSSE('test-workflow-id')

    await vi.advanceTimersByTimeAsync(3000)
    expect(store.currentWorkflow?.tasks[0].status).toBe('completed')
  })
})
