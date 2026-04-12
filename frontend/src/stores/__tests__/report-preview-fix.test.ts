import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useResearchStore } from '@/stores/research'
import { researchApi } from '@/api/client'
import { sseClient } from '@/api/sse'
import type { ResearchWorkflow } from '@/types'

vi.mock('@/api/client')
vi.mock('@/api/sse')

describe('ResearchStore - 报告预览修复测试', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('SSE result 事件 - 自动加载报告内容', () => {
    it('应该在收到 result 事件后自动加载报告内容', async () => {
      const store = useResearchStore()
      
      const workflow: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        status: 'running',
        tasks: [],
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow).mockResolvedValue(workflow)
      vi.mocked(researchApi.getReportContent).mockResolvedValue('# 测试报告\n\n报告内容')
      
      let resultCallback: ((event: any) => void) | undefined
      vi.mocked(sseClient.on).mockImplementation((event: string, callback: any) => {
        if (event === 'result') {
          resultCallback = callback
        }
      })
      
      await store.fetchWorkflow('test-workflow-id')
      store.connectSSE('test-workflow-id')
      
      // 模拟收到 result 事件
      if (resultCallback) {
        await resultCallback({
          data: {
            reportUrl: '/reports/test-report.md'
          }
        })
      }
      
      // 验证报告内容被加载
      expect(researchApi.getReportContent).toHaveBeenCalledWith('test-workflow-id')
      expect(store.currentWorkflow?.reportContent).toBe('# 测试报告\n\n报告内容')
    })
  })

  describe('轮询检测新 reportUrl - 自动加载报告内容', () => {
    it('应该在轮询检测到新 reportUrl 时自动加载报告内容', async () => {
      const store = useResearchStore()
      
      const workflowWithoutReport: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        status: 'running',
        tasks: [],
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      const workflowWithReport: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        status: 'all_success',
        tasks: [],
        reportUrl: '/reports/test-report.md',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow)
        .mockResolvedValueOnce(workflowWithoutReport)
        .mockResolvedValueOnce(workflowWithReport)
      vi.mocked(researchApi.getReportContent).mockResolvedValue('# 测试报告')
      
      await store.fetchWorkflow('test-workflow-id')
      
      // 验证初始状态没有报告
      expect(store.currentWorkflow?.reportUrl).toBeUndefined()
      
      // 启动轮询
      store.startPolling('test-workflow-id')
      
      // 等待轮询执行（3秒间隔）
      await new Promise(resolve => setTimeout(resolve, 3500))
      
      // 验证报告内容被加载
      expect(researchApi.getReportContent).toHaveBeenCalledWith('test-workflow-id')
      expect(store.currentWorkflow?.reportUrl).toBe('/reports/test-report.md')
      
      // 停止轮询
      store.stopPolling()
    })

    it('应该在已有 reportUrl 时不重复加载报告内容', async () => {
      const store = useResearchStore()
      
      const workflowWithReport: ResearchWorkflow = {
        workflowId: 'test-workflow-id',
        topic: '测试主题',
        status: 'all_success',
        tasks: [],
        reportUrl: '/reports/test-report.md',
        reportContent: '# 已有报告',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      }
      
      vi.mocked(researchApi.getWorkflow).mockResolvedValue(workflowWithReport)
      vi.mocked(researchApi.getReportContent).mockResolvedValue('# 新报告')
      
      await store.fetchWorkflow('test-workflow-id')
      
      // 清除之前的调用记录
      vi.mocked(researchApi.getReportContent).mockClear()
      
      // 启动轮询
      store.startPolling('test-workflow-id')
      
      // 等待轮询执行
      await new Promise(resolve => setTimeout(resolve, 3500))
      
      // 验证没有重复加载
      expect(researchApi.getReportContent).not.toHaveBeenCalled()
      
      // 停止轮询
      store.stopPolling()
    })
  })

  describe('页面加载 - 检查并加载报告内容', () => {
    it('当工作流已加载且有 reportUrl 但无 reportContent 时应该加载', async () => {
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
      vi.mocked(researchApi.getReportContent).mockResolvedValue('# 测试报告')
      
      // 第一次加载
      await store.fetchWorkflow('test-workflow-id')
      
      // 验证报告内容被加载
      expect(store.currentWorkflow?.reportContent).toBe('# 测试报告')
    })
  })
})
