import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ResearchWorkflow, Task, ScenarioMetadata, ScenarioUIConfig } from '@/types'
import { researchApi } from '@/api/client'
import { sseClient } from '@/api/sse'

/** 场景未提供 uiConfig 时的兜底文案 */
const DEFAULT_UI_CONFIG: ScenarioUIConfig = {
  navbarTitle: '研究助手',
  formTitle: '开始新的调研',
  topicLabel: '调研主题 *',
  topicPlaceholder: '例如：人工智能在医疗领域的应用'
}

/** 轮询基础间隔（毫秒） */
const POLL_BASE_INTERVAL = 3000
/** SSE 已确认可用后的低频兜底间隔（毫秒） */
const POLL_FALLBACK_INTERVAL = 5000
/** 连续失败达到该次数后停止轮询，避免无限请求 */
const POLL_MAX_FAILURES = 5
/** 失败退避的上限间隔（毫秒） */
const POLL_MAX_INTERVAL = 30000

/** 终态集合：进入这些状态后只需要等报告正文收敛 */
const TERMINAL_STATUSES = new Set(['all_success', 'partial_failed', 'all_failed', 'report_failed'])

/**
 * 调研核心 store：维护当前工作流快照、场景配置，并负责 SSE 与轮询两条数据通道。
 *
 * 数据来源有两个：SSE（实时增量）与轮询（兜底、防事件丢失），
 * 两者写同一份 currentWorkflow，因此更新时都采用合并而非整体替换。
 */
export const useResearchStore = defineStore('research', () => {
  const currentWorkflow = ref<ResearchWorkflow | null>(null)
  const scenarios = ref<ScenarioMetadata[]>([])
  const selectedScenarioId = ref<string | null>(null)
  const isLoading = ref(false)
  const isLoadingScenarios = ref(false)
  const error = ref<string | null>(null)
  /** 与 error 对应的业务错误码，供页面做差异化处理 */
  const errorCode = ref<string | null>(null)
  // 轮询定时器句柄，null 表示当前未轮询
  const pollingInterval = ref<number | null>(null)

  // 已建立 SSE 连接的工作流 id，用于幂等保护
  let connectedWorkflowId: string | null = null
  // 连续轮询失败次数，用于退避与熔断
  let pollingFailures = 0
  // 当前错误是否由轮询失败产生，成功一次后自动清除
  let pollingErrorActive = false
  // 当前轮询基础间隔：SSE 正常时用基础值，SSE 断开后降为低频兜底
  let pollIntervalMs = POLL_BASE_INTERVAL

  const currentWorkflowId = computed(() => currentWorkflow.value?.workflowId)
  const currentStatus = computed(() => currentWorkflow.value?.status)
  const tasks = computed(() => currentWorkflow.value?.tasks || [])
  const reportContent = computed(() => currentWorkflow.value?.reportContent || '')

  const selectedScenario = computed(() => {
    return scenarios.value.find((s) => s.scenarioId === selectedScenarioId.value)
  })

  /**
   * 场景文案配置：以默认文案为底，被选中场景的字段覆盖。
   * 场景未提供 uiConfig 时展开 undefined 不产生键，仍保留默认值。
   */
  const currentUIConfig = computed(() => {
    return {
      ...DEFAULT_UI_CONFIG,
      ...selectedScenario.value?.uiConfig
    }
  })

  /**
   * 统一写入错误信息。
   *
   * @param err 任意异常（API 层已归一化为 ApiError）
   * @param fallback 无可用信息时的兜底文案
   */
  function setError(err: unknown, fallback: string): void {
    error.value = err instanceof Error && err.message ? err.message : fallback
    const code = (err as { code?: unknown })?.code
    errorCode.value = typeof code === 'string' ? code : null
  }

  function clearError(): void {
    error.value = null
    errorCode.value = null
  }

  /**
   * 加载场景列表。
   * 失败仅记录日志不抛出：场景只影响文案，不应阻塞调研主流程。
   */
  async function loadScenarios(): Promise<void> {
    isLoadingScenarios.value = true
    try {
      scenarios.value = await researchApi.getScenarios()
      // 首次加载时默认选中第一个场景，后续请求需要带上该场景 id
      if (scenarios.value.length > 0 && !selectedScenarioId.value) {
        selectedScenarioId.value = scenarios.value[0].scenarioId
      }
    } catch (err) {
      console.error('[ResearchStore] Failed to load scenarios:', err)
    } finally {
      isLoadingScenarios.value = false
    }
  }

  /**
   * 计算下一次轮询延迟：失败后指数退避，上限 30 秒。
   */
  function nextPollDelay(): number {
    if (pollingFailures === 0) return pollIntervalMs
    return Math.min(pollIntervalMs * 2 ** pollingFailures, POLL_MAX_INTERVAL)
  }

  /**
   * 判断任务列表是否都已进入终态。
   * SSE 可能漏推 task_complete，因此不能只看工作流状态。
   */
  function tasksSettled(): boolean {
    const list = currentWorkflow.value?.tasks || []
    return list.every(
      (task) => task.status === 'completed' || task.status === 'failed' || task.status === 'skipped'
    )
  }

  /**
   * 判断当前工作流是否已经收敛到终态。
   * 有报告链接但正文尚未取到、或任务仍是 pending/running 时都不能停，
   * 否则页面会停留在旧的置灰状态。
   */
  function isSettled(): boolean {
    const workflow = currentWorkflow.value
    if (!workflow || !TERMINAL_STATUSES.has(workflow.status)) return false
    if (workflow.reportUrl && !workflow.reportContent) return false
    if (!tasksSettled()) return false
    return true
  }

  /**
   * 判断错误是否属于“工作流不存在”，此类错误继续轮询没有意义。
   */
  function isNotFoundError(err: unknown): boolean {
    const code = (err as { code?: unknown })?.code
    const status = (err as { status?: unknown })?.status
    return status === 404 || code === 'WORKFLOW_NOT_FOUND' || code === 'NOT_FOUND'
  }

  /**
   * 启动工作流轮询，作为 SSE 的兜底通道。
   * 已存在定时器时直接返回，保证幂等。
   *
   * @param workflowId 工作流 id
   */
  function startPolling(workflowId: string): void {
    // 幂等保护：页面进入与 SSE 建连都会触发，避免叠加多条定时器
    if (pollingInterval.value) return

    pollingFailures = 0
    pollingErrorActive = false
    pollIntervalMs = POLL_BASE_INTERVAL
    schedulePoll(workflowId)
    console.log(`[ResearchStore] Started polling for workflow ${workflowId}`)
  }

  /**
   * 切换到低频兜底轮询。
   *
   * SSE 在 plan 之后仍可能在报告阶段断开，因此不能直接停止轮询；
   * 这里只放大间隔，保证最终状态始终能被轮询收敛。
   *
   * @param workflowId 工作流 id
   */
  function shiftToFallbackPolling(workflowId: string): void {
    pollIntervalMs = POLL_FALLBACK_INTERVAL
    // 已有定时器时不必重建，下一轮会使用新的间隔
    if (!pollingInterval.value) {
      schedulePoll(workflowId)
    }
  }

  /**
   * 安排下一次轮询。使用 setTimeout 而非 setInterval，
   * 以便失败后按退避间隔重排。
   *
   * @param workflowId 工作流 id
   */
  function schedulePoll(workflowId: string): void {
    pollingInterval.value = window.setTimeout(async () => {
      pollingInterval.value = null

      try {
        await pollWorkflow(workflowId)
        pollingFailures = 0
        // 轮询恢复后清掉上一次由轮询写入的临时错误
        if (pollingErrorActive) {
          pollingErrorActive = false
          clearError()
        }
      } catch (err) {
        console.error('[Polling] Failed to fetch workflow:', err)

        if (isNotFoundError(err)) {
          setError(err, '工作流不存在或已被删除')
          stopPolling()
          return
        }

        pollingFailures += 1
        pollingErrorActive = true
        setError(err, '获取调研进度失败，正在重试...')

        if (pollingFailures >= POLL_MAX_FAILURES) {
          error.value = '无法获取调研进度，请稍后刷新页面重试'
          stopPolling()
          return
        }
      }

      // 终态且报告正文已收敛时停止轮询，避免无意义的持续请求
      if (isSettled()) {
        stopPolling()
        return
      }

      // 未停止时按当前退避级别安排下一轮
      if (currentWorkflow.value?.workflowId === workflowId) {
        schedulePoll(workflowId)
      }
    }, nextPollDelay())
  }

  /**
   * 拉取一次快照并按差异合并进 store。
   *
   * @param workflowId 工作流 id
   */
  async function pollWorkflow(workflowId: string): Promise<void> {
    const workflow = await researchApi.getWorkflow(
      workflowId,
      selectedScenarioId.value || undefined
    )
    const currentTasks = currentWorkflow.value?.tasks || []
    let shouldUpdate = false

    // 轮询快照与 SSE 增量可能交叉到达，这里先做差异比对：
    // 无变化就不替换 store，避免每次轮询触发整页重渲染
    if (currentWorkflow.value && workflow.status !== currentWorkflow.value.status) {
      shouldUpdate = true
    }

    // 报告正文可能晚于 report_url 就绪：只要本地没有正文就补拉
    const needsReportContent = Boolean(
      workflow.reportUrl && !currentWorkflow.value?.reportContent
    )

    if (workflow.tasks && workflow.tasks.length > 0) {
      if (workflow.tasks.length !== currentTasks.length) {
        shouldUpdate = true
      } else {
        // 数量一致时逐字段比较，任一状态、文本或时间戳变化都视为有更新
        const oldTaskMap = new Map(currentTasks.map((t) => [t.taskId, t]))
        for (const newTask of workflow.tasks) {
          const oldTask = oldTaskMap.get(newTask.taskId)
          if (!oldTask) {
            shouldUpdate = true
            break
          }
          if (
            newTask.status !== oldTask.status ||
            newTask.summary !== oldTask.summary ||
            newTask.sourcesSummary !== oldTask.sourcesSummary ||
            newTask.notices !== oldTask.notices ||
            newTask.startedAt !== oldTask.startedAt ||
            newTask.completedAt !== oldTask.completedAt
          ) {
            shouldUpdate = true
            break
          }
        }
      }
    }

    if (!shouldUpdate && !needsReportContent) return

    console.log(`[Polling] Workflow updated, refreshing data`)
    // 以已有任务为底做浅合并，保留前端由 SSE 写入的字段，
    // 再用轮询快照覆盖后端已确认的字段
    const updatedTasks = (workflow.tasks || []).map((newTask) => {
      const existing = currentTasks.find((t) => t.taskId === newTask.taskId)
      if (existing) {
        return { ...existing, ...newTask }
      }
      return newTask
    })
    currentWorkflow.value = {
      ...currentWorkflow.value!,
      ...workflow,
      // 快照偶尔不带任务，保留本地 SSE 已写入的任务，避免列表被清空
      tasks: (workflow.tasks || []).length > 0 ? updatedTasks : currentTasks,
      // 轮询快照可能不带正文，避免把已拉到的正文覆盖成 null
      reportContent: workflow.reportContent ?? currentWorkflow.value?.reportContent ?? null
    }

    // 轮询接口不一定内联报告正文，缺失时补拉
    if (needsReportContent) {
      await fetchReportContent(workflowId)
    }
  }

  function stopPolling(): void {
    if (pollingInterval.value) {
      window.clearTimeout(pollingInterval.value)
      pollingInterval.value = null
      console.log('[ResearchStore] Stopped polling')
    }
  }

  /**
   * 创建调研工作流，成功后拉取一次快照并建立 SSE 连接。
   *
   * 先 fetchWorkflow 再 connectSSE 的顺序不能颠倒：
   * SSE 的 plan 事件处理依赖 currentWorkflow 已存在，否则任务会被丢弃。
   *
   * @param topic 调研主题
   * @param description 可选详细描述
   * @returns 新建的工作流 id
   */
  async function createResearch(topic: string, description?: string): Promise<string> {
    isLoading.value = true
    clearError()

    try {
      const response = await researchApi.createResearch(
        { topic, description },
        selectedScenarioId.value || undefined
      )
      await fetchWorkflow(response.workflowId)
      connectSSE(response.workflowId)
      return response.workflowId
    } catch (err) {
      setError(err, '创建调研失败，请稍后重试')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 按 id 拉取工作流快照并写入 store。
   * 若快照中已带 reportUrl，会顺带拉取报告正文。
   *
   * @param workflowId 工作流 id
   */
  async function fetchWorkflow(workflowId: string): Promise<void> {
    isLoading.value = true
    clearError()

    // 切换到另一个工作流时，先断开旧的实时通道，避免旧事件串入
    if (currentWorkflow.value && currentWorkflow.value.workflowId !== workflowId) {
      disconnectSSE()
    }

    try {
      const workflow = await researchApi.getWorkflow(
        workflowId,
        selectedScenarioId.value || undefined
      )
      currentWorkflow.value = workflow

      if (workflow.tasks && workflow.tasks.length > 0) {
        console.log(
          `[ResearchStore] Fetched ${workflow.tasks.length} tasks from backend for workflow ${workflowId}`
        )
      } else {
        console.log(
          `[ResearchStore] No tasks found for workflow ${workflowId}, waiting for plan event...`
        )
      }

      if (workflow.reportUrl) {
        await fetchReportContent(workflowId)
      }
    } catch (err) {
      setError(err, '获取工作流失败，请稍后重试')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 拉取报告正文并写入 currentWorkflow。
   * 仅在已有 reportUrl 时发起请求；失败只记录日志，避免打断正在进行的流式渲染。
   *
   * @param workflowId 工作流 id
   */
  async function fetchReportContent(workflowId: string): Promise<boolean> {
    if (!currentWorkflow.value?.reportUrl) return false

    try {
      // 未选择场景时不传第二个参数，避免把 undefined 显式传给 API
      const content = selectedScenarioId.value
        ? await researchApi.getReportContent(workflowId, selectedScenarioId.value)
        : await researchApi.getReportContent(workflowId)
      if (currentWorkflow.value) {
        currentWorkflow.value.reportContent = content
      }
      return true
    } catch (err) {
      console.error('[ResearchStore] Failed to fetch report content:', err)
      return false
    }
  }

  /**
   * 带退避地拉取报告正文。
   *
   * result 事件早于后端把 report_url 落库（收尾阶段才写库），
   * 首次请求可能 404，因此按 1s/2s/4s/8s/10s 重试。
   *
   * @param workflowId 工作流 id
   * @returns 是否成功拉到正文
   */
  async function fetchReportContentWithRetry(workflowId: string): Promise<boolean> {
    const delays = [0, 1000, 2000, 4000, 8000, 10000]
    for (const delayMs of delays) {
      if (delayMs > 0) {
        await new Promise((resolve) => window.setTimeout(resolve, delayMs))
      }
      if (await fetchReportContent(workflowId)) return true
    }
    return false
  }

  /**
   * 建立 SSE 连接并注册各类型事件处理器，同时启动轮询兜底。
   *
   * sseClient.on 是追加语义：这里先清空旧处理器并做幂等判断，
   * 保证同一工作流连接一次、切换工作流时不会残留旧回调。
   *
   * @param workflowId 工作流 id
   */
  function connectSSE(workflowId: string): void {
    if (connectedWorkflowId === workflowId) {
      // 已连接同一工作流：只确保轮询兜底没有被提前停掉
      startPolling(workflowId)
      return
    }

    sseClient.clearHandlers()
    sseClient.connect(workflowId, selectedScenarioId.value || undefined)
    connectedWorkflowId = workflowId

    // 连接彻底关闭（非自动重连）时恢复低频轮询，避免页面永远停在最后一个事件
    sseClient.onConnectionError((closed) => {
      if (!closed) return

      console.warn('[SSE] 连接已关闭，切换为轮询兜底')
      if (isSettled()) return
      shiftToFallbackPolling(workflowId)
    })

    // 计划生成完成：用完整任务列表覆盖，并停止轮询兜底
    sseClient.on('plan', (event) => {
      const rawTasks = Array.isArray(event.data?.tasks) ? event.data.tasks : []
      console.log('[SSE] Received plan event with', rawTasks.length, 'tasks')
      if (currentWorkflow.value) {
        const tasks = rawTasks.map((t: any) => ({
          taskId: t.task_id || t.taskId,
          title: t.title,
          intent: t.intent,
          query: t.query,
          order: t.order,
          dependsOn: t.depends_on || t.dependsOn || [],
          status: t.status || 'pending',
          summary: t.summary,
          sourcesSummary: t.sources_summary || t.sourcesSummary,
          notices: t.notices,
          createdAt: t.created_at || t.createdAt,
          updatedAt: t.updated_at || t.updatedAt,
          startedAt: t.started_at || t.startedAt,
          completedAt: t.completed_at || t.completedAt
        }))
        currentWorkflow.value = {
          ...currentWorkflow.value,
          tasks
        }
        // SSE 已确认可用，但报告阶段仍可能断流：降为低频兜底而非完全停止
        shiftToFallbackPolling(workflowId)
      }
    })

    // 单任务开始：局部更新该任务，避免整体替换引起列表重渲染；
    // 事件字段可能是 camelCase 或 snake_case，两种都兼容
    sseClient.on('task_start', (event) => {
      const taskId = event.data?.taskId || event.data?.task_id
      if (!taskId) return
      updateTask(taskId, { status: 'running', startedAt: new Date().toISOString() })
    })

    // 单任务完成：写入摘要、来源与通知，并记录前端收到事件的时间
    sseClient.on('task_complete', (event) => {
      const taskId = event.data?.taskId || event.data?.task_id
      if (!taskId) return
      updateTask(taskId, {
        status: 'completed',
        summary: event.data.summary,
        sourcesSummary: event.data.sourcesSummary || event.data.sources_summary,
        notices: event.data.notices,
        completedAt: new Date().toISOString()
      })
    })

    // 报告正文分片下发，按到达顺序累加；
    // result 到达后还会用完整正文覆盖一次，所以这里不重复处理分片去重
    sseClient.on('chunk', (event) => {
      const content = typeof event.data?.content === 'string' ? event.data.content : ''
      if (!content || !currentWorkflow.value) return
      currentWorkflow.value.reportContent = (currentWorkflow.value.reportContent || '') + content
    })

    // 流程结束：状态置为成功，带重试拉取完整正文，再关闭 SSE
    sseClient.on('result', async (event) => {
      const reportUrl = event.data?.reportUrl || event.data?.report_url
      if (currentWorkflow.value) {
        currentWorkflow.value.status = 'all_success'
        if (reportUrl) {
          currentWorkflow.value.reportUrl = reportUrl
        }
      }

      // 后端要等整个图收尾后才写 report_url，这里必须重试而不是只拉一次
      await fetchReportContentWithRetry(workflowId)

      // result 事件不代表任务快照已同步：关闭 SSE 前再拉一次完整快照
      try {
        await pollWorkflow(workflowId)
      } catch (err) {
        console.error('[ResearchStore] Failed to sync workflow after result:', err)
      }

      sseClient.disconnect()
      connectedWorkflowId = null

      if (isSettled()) {
        stopPolling()
      } else {
        // 任务或正文尚未收敛，保留低频轮询继续兜底
        shiftToFallbackPolling(workflowId)
      }
    })

    // 业务失败事件（区别于 EventSource 的网络层 onerror）：标记失败并断开
    sseClient.on('error', (event) => {
      if (currentWorkflow.value) {
        currentWorkflow.value.status = 'all_failed'
      }
      error.value = event.data?.message || '工作流执行失败，请稍后重试'
      errorCode.value = event.data?.error_code || 'WORKFLOW_EXECUTION_FAILED'
      stopPolling()
      sseClient.disconnect()
      connectedWorkflowId = null
    })

    // 同时开启轮询兜底：SSE 若因网络中断漏推事件，靠轮询收敛最终状态
    startPolling(workflowId)
  }

  /**
   * 局部更新指定任务。
   * 找不到对应任务时静默忽略：事件可能先于工作流快照到达，或属于其他实例。
   *
   * @param taskId 目标任务 id
   * @param updates 需要覆盖的任务字段
   */
  function updateTask(taskId: string, updates: Partial<Task>): void {
    if (!currentWorkflow.value) return

    const tasks = currentWorkflow.value.tasks
    const taskIndex = tasks.findIndex((task) => task.taskId === taskId)
    if (taskIndex !== -1) {
      const updatedTasks = tasks.map((task, index) =>
        index === taskIndex ? { ...task, ...updates } : task
      )
      currentWorkflow.value = {
        ...currentWorkflow.value,
        tasks: updatedTasks
      }
    }
  }

  /**
   * 断开数据通道（SSE + 轮询），页面卸载时调用以防后台继续请求。
   */
  function disconnectSSE(): void {
    sseClient.disconnect()
    connectedWorkflowId = null
    stopPolling()
  }

  /**
   * 重置 store 到初始状态，用于开始新的调研。
   */
  function reset(): void {
    disconnectSSE()
    sseClient.clearHandlers()
    currentWorkflow.value = null
    pollingFailures = 0
    pollingErrorActive = false
    clearError()
  }

  return {
    currentWorkflow,
    scenarios,
    selectedScenarioId,
    selectedScenario,
    currentUIConfig,
    isLoading,
    isLoadingScenarios,
    error,
    errorCode,
    currentWorkflowId,
    currentStatus,
    tasks,
    reportContent,
    loadScenarios,
    createResearch,
    fetchWorkflow,
    fetchReportContent,
    connectSSE,
    disconnectSSE,
    reset,
    startPolling,
    stopPolling
  }
})
