import type { SSEEvent, SSEEventType } from '@/types'

/**
 * SSE 事件回调签名。
 */
type EventHandler = (event: SSEEvent) => void

/** 后端会以命名事件（event: plan 等）下发，需要逐个监听。 */
const KNOWN_EVENT_TYPES: SSEEventType[] = [
  'plan',
  'task_start',
  'task_complete',
  'chunk',
  'result',
  'error'
]

/**
 * 调研进度的 SSE 客户端。
 *
 * 后端使用命名事件（`event: plan` + `data: {...}`），因此不能只依赖 onmessage；
 * 这里同时监听命名事件与默认 message，并兼容数据体自带 type 的旧格式。
 * 单个处理器的异常不会影响其他订阅者。
 */
export class SSEClient {
  private eventSource: EventSource | null = null
  /** 按事件类型登记的处理器集合 */
  private eventHandlers: Map<SSEEventType, EventHandler[]> = new Map()
  /** 订阅全部事件的处理器集合 */
  private allEventHandler: EventHandler[] = []
  /** 连接错误回调：参数表示连接是否已被彻底关闭（false 时浏览器会自动重连） */
  private connectionErrorHandler: ((closed: boolean) => void) | null = null
  /** 连接建立回调 */
  private openHandler: (() => void) | null = null

  /**
   * 建立到指定工作流的 SSE 连接。
   * 若已有连接会先关闭，保证同一实例只持有一个底层 EventSource。
   *
   * @param workflowId 工作流 id
   * @param scenarioId 可选场景 id，后端按场景隔离数据
   */
  connect(workflowId: string, scenarioId?: string): void {
    this.disconnect()

    const query = scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : ''
    const source = new EventSource(`/api/research/${encodeURIComponent(workflowId)}/stream${query}`)
    this.eventSource = source

    // 命名事件：后端每条消息都有 event 字段，onmessage 收不到
    KNOWN_EVENT_TYPES.forEach((type) => {
      source.addEventListener(type, (event) => {
        this.handleRawEvent(type, event as MessageEvent)
      })
    })

    // 兼容未命名事件与自带 type 的数据体
    source.onmessage = (event) => this.handleRawEvent(undefined, event)

    source.onopen = () => {
      this.openHandler?.()
    }

    // 网络层错误交给浏览器 EventSource 自动重连；仅在彻底关闭时通知上层
    source.onerror = () => {
      this.connectionErrorHandler?.(source.readyState === EventSource.CLOSED)
    }
  }

  /**
   * 关闭当前连接并释放引用，避免后台继续接收事件或自动重连。
   */
  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
  }

  /**
   * 清空所有业务事件处理器。
   * 切换工作流前调用，避免旧页面的处理器继续响应新连接的事件。
   */
  clearHandlers(): void {
    this.eventHandlers.clear()
    this.allEventHandler = []
  }

  /**
   * 订阅指定类型的事件。
   * 处理器为追加语义，同一回调重复注册会被多次调用，调用方需自行保证只注册一次。
   *
   * @param eventType 事件类型
   * @param handler 事件回调
   */
  on(eventType: SSEEventType, handler: EventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, [])
    }
    this.eventHandlers.get(eventType)!.push(handler)
  }

  /**
   * 取消订阅指定类型的事件（按引用匹配）。
   *
   * @param eventType 事件类型
   * @param handler 注册时传入的同一个回调引用
   */
  off(eventType: SSEEventType, handler: EventHandler): void {
    const handlers = this.eventHandlers.get(eventType)
    if (handlers) {
      this.eventHandlers.set(
        eventType,
        handlers.filter((h) => h !== handler)
      )
    }
  }

  /**
   * 订阅全部类型的事件。
   *
   * @param handler 事件回调
   */
  onAny(handler: EventHandler): void {
    this.allEventHandler.push(handler)
  }

  /**
   * 取消订阅全部类型的事件（按引用匹配）。
   *
   * @param handler 注册时传入的同一个回调引用
   */
  offAny(handler: EventHandler): void {
    this.allEventHandler = this.allEventHandler.filter((h) => h !== handler)
  }

  /**
   * 注册连接错误回调（替换语义）。
   *
   * @param handler 接收连接是否彻底关闭
   */
  onConnectionError(handler: (closed: boolean) => void): void {
    this.connectionErrorHandler = handler
  }

  /**
   * 注册连接建立回调（替换语义）。
   *
   * @param handler 连接建立后的回调
   */
  onOpen(handler: () => void): void {
    this.openHandler = handler
  }

  /**
   * 解析并分发一条原始消息。
   *
   * @param namedType 命名事件类型；未命名消息为 undefined
   * @param message 浏览器原始消息事件
   */
  private handleRawEvent(namedType: SSEEventType | undefined, message: MessageEvent): void {
    if (!message.data) return

    let parsed: any
    try {
      parsed = JSON.parse(message.data)
    } catch (error) {
      // 心跳/非 JSON 帧只记录日志，不应中断连接
      console.error('[SSE] 事件解析失败，已忽略:', error)
      return
    }

    // 兼容 {type, data} 包装格式：仅当两者同时存在时才解包
    const payload =
      parsed && typeof parsed === 'object' && parsed.type && 'data' in parsed ? parsed.data : parsed
    const eventType = (namedType || parsed?.type) as SSEEventType | undefined
    if (!eventType) return

    this.dispatchEvent({ type: eventType, data: payload ?? {} })
  }

  /**
   * 分发事件：先通知该类型的处理器，再通知 onAny 的处理器。
   * 单个处理器抛异常只记录日志，避免连带影响其他订阅者。
   *
   * @param event 已解析的事件对象
   */
  private dispatchEvent(event: SSEEvent): void {
    const handlers = this.eventHandlers.get(event.type) || []
    handlers.forEach((handler) => {
      try {
        handler(event)
      } catch (error) {
        console.error(`[SSE] ${event.type} 事件处理器异常:`, error)
      }
    })

    this.allEventHandler.forEach((handler) => {
      try {
        handler(event)
      } catch (error) {
        console.error('[SSE] onAny 事件处理器异常:', error)
      }
    })
  }
}

// 单例：全局只保留一条 SSE 连接，避免多个页面/组件重复建连
export const sseClient = new SSEClient()
