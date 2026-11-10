import { afterEach, describe, expect, it, vi } from 'vitest'
import apiClient, { ApiError, extractReportId, researchApi, toApiError } from '@/api/client'

/** 构造一个 axios 风格的错误对象，避免真实网络请求 */
function axiosError(status: number, data: unknown) {
  return { isAxiosError: true, message: 'Request failed', response: { status, data } }
}

describe('extractReportId', () => {
  it('应该从带 /research/reports 前缀的地址中取文件名', () => {
    expect(extractReportId('/research/reports/abc.md')).toBe('abc.md')
  })

  it('应该兼容 dev_survey 的 /dev-research 前缀与查询串', () => {
    expect(extractReportId('/dev-research/reports/abc.md?t=1')).toBe('abc.md')
  })

  it('空地址应返回空字符串', () => {
    expect(extractReportId('')).toBe('')
  })
})

describe('toApiError', () => {
  it('应该解析统一错误体', () => {
    const error = toApiError(
      axiosError(404, {
        error_code: 'WORKFLOW_NOT_FOUND',
        message: '工作流不存在或已被删除',
        details: null
      })
    )

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('WORKFLOW_NOT_FOUND')
    expect(error.message).toBe('工作流不存在或已被删除')
    expect(error.status).toBe(404)
  })

  it('应该解析 FastAPI 校验错误数组', () => {
    const error = toApiError(
      axiosError(422, { detail: [{ loc: ['body', 'topic'], msg: 'too long' }] })
    )

    expect(error.code).toBe('VALIDATION_ERROR')
    expect(error.details).toContain('topic: too long')
    expect(error.message).toBe('请求参数有误，请检查后重试')
  })

  it('应该解析 detail 为字符串的 HTTPException', () => {
    const error = toApiError(axiosError(400, { detail: '报告 ID 无效' }))

    expect(error.message).toBe('报告 ID 无效')
    expect(error.code).toBe('INVALID_REQUEST')
  })

  it('无响应体时应按状态码兜底', () => {
    const error = toApiError(axiosError(503, 'Service Unavailable'))

    expect(error.code).toBe('SERVICE_UNAVAILABLE')
    expect(error.message).toBe('服务暂时不可用，请稍后重试')
  })

  it('网络不可用时应提示检查网络', () => {
    const error = toApiError({ isAxiosError: true, message: 'Network Error' })

    expect(error.code).toBe('NETWORK_ERROR')
    expect(error.message).toContain('网络')
  })

  it('超时错误应有独立错误码', () => {
    const error = toApiError({ isAxiosError: true, code: 'ECONNABORTED', message: 'timeout' })

    expect(error.code).toBe('TIMEOUT')
  })

  it('普通异常应保留原始信息', () => {
    const error = toApiError(new Error('未知失败'))

    expect(error.code).toBe('CLIENT_ERROR')
    expect(error.message).toBe('未知失败')
  })
})

describe('researchApi.downloadReport', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('应该通过 /api 下载接口并携带场景参数', async () => {
    const blob = new Blob(['# 报告'], { type: 'text/markdown' })
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: blob })

    const result = await researchApi.downloadReport('/dev-research/reports/abc.md', 'dev_survey')

    expect(getSpy).toHaveBeenCalledWith('/research/reports/abc.md', {
      params: { scenario_id: 'dev_survey' },
      responseType: 'blob'
    })
    expect(result).toBe(blob)
  })

  it('非法报告地址应直接抛出 ApiError', async () => {
    await expect(researchApi.downloadReport('')).rejects.toMatchObject({
      code: 'INVALID_REPORT_ID'
    })
  })
})
