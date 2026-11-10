import { describe, it, expect } from 'vitest'
import { mapWorkflowStatusToDisplay, type WorkflowStatus } from '@/types'

describe('mapWorkflowStatusToDisplay', () => {
  it('应该将 pending 映射为 pending', () => {
    expect(mapWorkflowStatusToDisplay('pending')).toBe('pending')
  })

  it('应该将 running 映射为 running', () => {
    expect(mapWorkflowStatusToDisplay('running')).toBe('running')
  })

  it('应该将 all_success 映射为 completed', () => {
    expect(mapWorkflowStatusToDisplay('all_success')).toBe('completed')
  })

  it('应该将 partial_failed 映射为 completed', () => {
    expect(mapWorkflowStatusToDisplay('partial_failed')).toBe('completed')
  })

  it('应该将 all_failed 映射为 failed', () => {
    expect(mapWorkflowStatusToDisplay('all_failed')).toBe('failed')
  })

  it('应该将 report_failed 映射为 failed', () => {
    expect(mapWorkflowStatusToDisplay('report_failed')).toBe('failed')
  })
})

describe('WorkflowStatus 类型', () => {
  it('应该接受所有有效的状态值', () => {
    const validStatuses: WorkflowStatus[] = [
      'pending',
      'running',
      'all_success',
      'partial_failed',
      'all_failed',
      'report_failed'
    ]

    validStatuses.forEach((status) => {
      const displayStatus = mapWorkflowStatusToDisplay(status)
      expect(['pending', 'running', 'completed', 'failed']).toContain(displayStatus)
    })
  })
})
