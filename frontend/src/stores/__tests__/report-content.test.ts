import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useResearchStore } from '@/stores/research'
import { researchApi } from '@/api/client'
import type { ResearchWorkflow } from '@/types'

vi.mock('@/api/client')
vi.mock('@/api/sse')

describe('ResearchStore - 报告内容加载', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchReportContent', () => {
    it('应该成功加载报告内容', async () => {
      const store = useResearchStore()

      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'all_success',
        tasks: [],
        reportUrl: '/reports/test-report.md',
        reportContent: '',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }

      vi.mocked(researchApi.getWorkflow).mockResolvedValue(workflow)
      vi.mocked(researchApi.getReportContent).mockResolvedValue('# 测试报告\n\n这是报告内容')

      await store.fetchWorkflow('test-workflow-id')

      expect(store.currentWorkflow?.reportContent).toBe('# 测试报告\n\n这是报告内容')
      expect(researchApi.getReportContent).toHaveBeenCalledWith('test-workflow-id')
    })

    it('当没有 reportUrl 时不应该加载报告内容', async () => {
      const store = useResearchStore()

      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'running',
        tasks: [],
        reportUrl: undefined,
        reportContent: '',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }

      vi.mocked(researchApi.getWorkflow).mockResolvedValue(workflow)

      await store.fetchWorkflow('test-workflow-id')

      expect(researchApi.getReportContent).not.toHaveBeenCalled()
    })

    it('加载报告内容失败时不应该中断工作流加载', async () => {
      const store = useResearchStore()

      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        description: '测试描述',
        status: 'all_success',
        tasks: [],
        reportUrl: '/reports/test-report.md',
        reportContent: '',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }

      vi.mocked(researchApi.getWorkflow).mockResolvedValue(workflow)
      vi.mocked(researchApi.getReportContent).mockRejectedValue(new Error('加载失败'))

      await store.fetchWorkflow('test-workflow-id')

      expect(store.currentWorkflow).not.toBeNull()
      expect(store.currentWorkflow?.workflowId).toBe('test-workflow-id')
    })
  })

  describe('API 客户端 - getReportContent', () => {
    it('应该调用正确的 API 端点', async () => {
      const store = useResearchStore()

      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        status: 'all_success',
        tasks: [],
        reportUrl: '/reports/test-report.md',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }

      vi.mocked(researchApi.getWorkflow).mockResolvedValue(workflow)
      vi.mocked(researchApi.getReportContent).mockResolvedValue('报告内容')

      await store.fetchWorkflow('test-workflow-id')

      expect(researchApi.getReportContent).toHaveBeenCalledWith('test-workflow-id')
    })
  })
})
