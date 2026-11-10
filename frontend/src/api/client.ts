import axios from 'axios'
import type { CreateResearchRequest, ResearchWorkflow, Task, ScenarioMetadata } from '@/types'

/**
 * 业务错误码到中文提示的兜底映射。
 * 后端已返回 message 时优先使用后端文案，这里只覆盖缺省场景。
 */
const ERROR_CODE_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: '请求参数有误，请检查后重试',
  INVALID_REQUEST: '请求参数有误，请检查后重试',
  INVALID_WORKFLOW_ID: '工作流 ID 无效',
  INVALID_REPORT_ID: '报告 ID 无效',
  SCENARIO_NOT_FOUND: '场景不存在',
  WORKFLOW_NOT_FOUND: '工作流不存在或已被删除',
  REPORT_NOT_FOUND: '报告尚未生成',
  TRACE_NOT_FOUND: '该工作流暂无追踪记录',
  CHECKPOINT_UNAVAILABLE: '服务暂时不可用，请稍后重试',
  INVALID_SCENARIO_RESPONSE: '后端返回数据异常，请稍后重试',
  SERVICE_UNAVAILABLE: '服务暂时不可用，请稍后重试',
  INTERNAL_ERROR: '服务器内部错误，请稍后重试',
  NETWORK_ERROR: '网络连接失败，请检查网络后重试',
  TIMEOUT: '请求超时，请稍后重试'
}

/**
 * 统一的前端业务异常。
 * 携带 errorCode 便于上层做差异化处理（如 404 停止轮询）。
 */
export class ApiError extends Error {
  readonly code: string
  readonly status?: number
  readonly details?: string

  constructor(message: string, options: { code?: string; status?: number; details?: string } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = options.code || 'UNKNOWN_ERROR'
    this.status = options.status
    this.details = options.details
  }
}

/** HTTP 状态码到业务错误码的兜底映射（响应体无法解析时使用）。 */
function statusToCode(status?: number): string {
  switch (status) {
    case 400:
      return 'INVALID_REQUEST'
    case 404:
      return 'NOT_FOUND'
    case 422:
      return 'VALIDATION_ERROR'
    case 500:
      return 'INTERNAL_ERROR'
    case 503:
      return 'SERVICE_UNAVAILABLE'
    default:
      return status && status >= 500 ? 'INTERNAL_ERROR' : 'REQUEST_FAILED'
  }
}

/**
 * 解析后端错误响应体，兼容三种历史格式：
 * 1. 统一错误体 {error_code, message, details}
 * 2. HTTPException 包装 {detail: {error_code, message, details}}
 * 3. FastAPI 默认校验错误 {detail: [{loc, msg}]}
 */
function parseErrorBody(data: any): { code?: string; message?: string; details?: string } {
  if (!data || typeof data !== 'object') return {}

  if (typeof data.error_code === 'string') {
    return {
      code: data.error_code,
      message: typeof data.message === 'string' ? data.message : undefined,
      details: typeof data.details === 'string' ? data.details : undefined
    }
  }

  const detail = data.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    if (typeof detail.error_code === 'string') {
      return {
        code: detail.error_code,
        message: typeof detail.message === 'string' ? detail.message : undefined,
        details: typeof detail.details === 'string' ? detail.details : undefined
      }
    }
    return {}
  }

  if (typeof detail === 'string') {
    return { message: detail }
  }

  if (Array.isArray(detail)) {
    const parts = detail
      .map((item: any) => {
        const location = Array.isArray(item?.loc)
          ? item.loc
              .filter((key: unknown) => !['body', 'query', 'path'].includes(String(key)))
              .join('.')
          : ''
        const message = typeof item?.msg === 'string' ? item.msg : ''
        return location && message ? `${location}: ${message}` : message
      })
      .filter(Boolean)
    return parts.length ? { details: parts.join('; ') } : {}
  }

  return {}
}

/** 把任意异常统一转换为 ApiError，保证上层拿到的永远是中文可展示信息。 */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return new ApiError(ERROR_CODE_MESSAGES.TIMEOUT, { code: 'TIMEOUT' })
    }

    const response = error.response
    if (!response) {
      return new ApiError(ERROR_CODE_MESSAGES.NETWORK_ERROR, { code: 'NETWORK_ERROR' })
    }

    const parsed = parseErrorBody(response.data)
    const code = parsed.code || statusToCode(response.status)
    const message = parsed.message || ERROR_CODE_MESSAGES[code] || '请求失败，请稍后重试'
    return new ApiError(message, { code, status: response.status, details: parsed.details })
  }

  if (error instanceof Error) {
    return new ApiError(error.message || '请求失败，请稍后重试', { code: 'CLIENT_ERROR' })
  }

  return new ApiError('请求失败，请稍后重试', { code: 'UNKNOWN_ERROR' })
}

/**
 * 后端 REST API 的 axios 实例。
 *
 * 统一走 `/api` 前缀（由 Vite 代理或网关转发到后端），
 * 默认以 JSON 交互；业务层不直接使用 axios，而是通过下方 researchApi。
 */
const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 所有失败响应先归一化为 ApiError，避免各调用点重复解析后端错误结构
apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(toApiError(error))
)

/**
 * 将后端返回的任务对象（snake_case）转换为前端 Task（camelCase）。
 *
 * @param task 后端原始任务对象
 * @returns 字段名已归一化的任务
 */
function transformTaskFromBackend(task: any): Task {
  return {
    taskId: task?.task_id ?? task?.taskId ?? '',
    title: task?.title ?? '',
    intent: task?.intent ?? '',
    query: task?.query ?? '',
    order: task?.order ?? 0,
    dependsOn: task?.depends_on ?? task?.dependsOn ?? [],
    status: task?.status ?? 'pending',
    summary: task?.summary,
    sourcesSummary: task?.sources_summary ?? task?.sourcesSummary,
    notices: task?.notices,
    createdAt: task?.created_at ?? task?.createdAt,
    updatedAt: task?.updated_at ?? task?.updatedAt,
    startedAt: task?.started_at ?? task?.startedAt,
    completedAt: task?.completed_at ?? task?.completedAt
  }
}

/**
 * 将后端返回的工作流对象转换为前端 ResearchWorkflow。
 *
 * @param data 后端原始工作流对象
 * @returns 字段名已归一化、任务列表已逐项转换的工作流
 */
function transformWorkflowFromBackend(data: any): ResearchWorkflow {
  if (!data || typeof data !== 'object' || !data.workflow_id) {
    throw new ApiError(ERROR_CODE_MESSAGES.INVALID_SCENARIO_RESPONSE, {
      code: 'INVALID_SCENARIO_RESPONSE'
    })
  }

  return {
    workflowId: data.workflow_id,
    topic: data.topic ?? '',
    description: data.description ?? undefined,
    status: data.status ?? 'pending',
    // 未规划出任务时统一兜底为空数组，避免上层遍历时判空
    tasks: Array.isArray(data.tasks) ? data.tasks.map(transformTaskFromBackend) : [],
    reportUrl: data.report_url ?? undefined,
    reportContent: data.report_content ?? undefined,
    createdAt: data.created_at,
    updatedAt: data.updated_at
  }
}

/**
 * 将后端返回的场景元数据转换为前端 ScenarioMetadata。
 *
 * @param data 后端原始场景对象
 * @returns 场景元数据；uiConfig 缺失时保持 undefined，由 store 回退到默认文案
 */
function transformScenarioFromBackend(data: any): ScenarioMetadata {
  return {
    scenarioId: data?.scenario_id,
    name: data?.name,
    description: data?.description,
    version: data?.version,
    author: data?.author,
    uiConfig: data?.ui_config
      ? {
          navbarTitle: data.ui_config.navbar_title,
          formTitle: data.ui_config.form_title,
          topicLabel: data.ui_config.topic_label,
          topicPlaceholder: data.ui_config.topic_placeholder
        }
      : undefined
  }
}

/**
 * 从后端返回的报告地址中提取文件名。
 *
 * report_url 可能带 `/research/reports` 或 `/dev-research/reports` 前缀，
 * 下载接口只接受文件名，因此统一取路径最后一段。
 */
export function extractReportId(reportUrl: string): string {
  if (!reportUrl) return ''
  const path = reportUrl.split(/[?#]/)[0]
  const segments = path.split('/').filter(Boolean)
  if (segments.length === 0) return ''
  try {
    return decodeURIComponent(segments[segments.length - 1])
  } catch {
    return segments[segments.length - 1]
  }
}

/**
 * 调研相关接口集合。
 * 除创建接口外，其余接口都接受可选的 scenarioId（以 query 形式传递），
 * 用于后端按场景隔离数据。
 */
export const researchApi = {
  /**
   * 获取所有可用场景，用于渲染导航栏与表单文案。
   *
   * @returns 场景元数据列表
   */
  getScenarios: async (): Promise<ScenarioMetadata[]> => {
    const response = await apiClient.get('/research/scenarios')
    const scenarios = response.data?.scenarios
    if (!Array.isArray(scenarios)) {
      throw new ApiError(ERROR_CODE_MESSAGES.INVALID_SCENARIO_RESPONSE, {
        code: 'INVALID_SCENARIO_RESPONSE'
      })
    }
    return scenarios.map(transformScenarioFromBackend)
  },

  /**
   * 创建调研工作流。
   *
   * @param request 调研主题与可选详细描述
   * @param scenarioId 可选场景 id，未指定时后端使用默认场景
   * @returns 新建工作流的 id
   */
  createResearch: async (
    request: CreateResearchRequest,
    scenarioId?: string
  ): Promise<{ workflowId: string }> => {
    const params = scenarioId ? { scenario_id: scenarioId } : {}
    const response = await apiClient.post('/research', request, { params })
    const workflowId = response.data?.workflow_id
    if (!workflowId) {
      throw new ApiError(ERROR_CODE_MESSAGES.INVALID_SCENARIO_RESPONSE, {
        code: 'INVALID_SCENARIO_RESPONSE'
      })
    }
    return { workflowId }
  },

  /**
   * 获取工作流快照（含任务列表、状态与报告地址）。
   * 首次进入详情页与轮询兜底均复用该接口。
   *
   * @param workflowId 工作流 id
   * @param scenarioId 可选场景 id
   * @returns 归一化后的工作流
   */
  getWorkflow: async (workflowId: string, scenarioId?: string): Promise<ResearchWorkflow> => {
    const params = scenarioId ? { scenario_id: scenarioId } : {}
    const response = await apiClient.get(`/research/${workflowId}`, { params })
    return transformWorkflowFromBackend(response.data)
  },

  /**
   * 获取报告正文。
   * 工作流里只给出 reportUrl、不内联正文，因此导出/预览前需单独拉取。
   *
   * @param workflowId 工作流 id
   * @param scenarioId 可选场景 id
   * @returns Markdown 格式的报告正文
   */
  getReportContent: async (workflowId: string, scenarioId?: string): Promise<string> => {
    const params = scenarioId ? { scenario_id: scenarioId } : {}
    const response = await apiClient.get(`/research/${workflowId}/report-content`, { params })
    const content = response.data?.content
    return typeof content === 'string' ? content : ''
  },

  /**
   * 下载报告文件。
   *
   * 必须经由 `/api` 代理请求后端下载接口：report_url 是后端静态路径，
   * 前端直接打开会绕过代理并导致 404（dev_survey 的 `/dev-research` 前缀同理）。
   *
   * @param reportUrl 工作流快照中的报告地址
   * @param scenarioId 可选场景 id
   * @returns 报告文件的二进制内容
   */
  downloadReport: async (reportUrl: string, scenarioId?: string): Promise<Blob> => {
    const reportId = extractReportId(reportUrl)
    if (!reportId) {
      throw new ApiError(ERROR_CODE_MESSAGES.INVALID_REPORT_ID, { code: 'INVALID_REPORT_ID' })
    }
    const params = scenarioId ? { scenario_id: scenarioId } : {}
    const response = await apiClient.get(`/research/reports/${encodeURIComponent(reportId)}`, {
      params,
      responseType: 'blob'
    })
    return response.data as Blob
  }
}

export default apiClient
