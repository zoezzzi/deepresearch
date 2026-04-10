import type { SSEEvent, SSEEventType } from '@/types'

type EventHandler = (event: SSEEvent) => void

export class SSEClient {
  private eventSource: EventSource | null = null
  private eventHandlers: Map<SSEEventType, EventHandler[]> = new Map()
  private allEventHandler: EventHandler[] = []

  connect(workflowId: string): void {
    if (this.eventSource) {
      this.disconnect()
    }

    this.eventSource = new EventSource(`/api/research/${workflowId}/stream`)

    this.eventSource.onmessage = (event) => {
      try {
        const parsedEvent: SSEEvent = JSON.parse(event.data)
        this.dispatchEvent(parsedEvent)
      } catch (error) {
        console.error('Failed to parse SSE event:', error)
      }
    }

    this.eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)
    }
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
  }

  on(eventType: SSEEventType, handler: EventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, [])
    }
    this.eventHandlers.get(eventType)!.push(handler)
  }

  off(eventType: SSEEventType, handler: EventHandler): void {
    const handlers = this.eventHandlers.get(eventType)
    if (handlers) {
      this.eventHandlers.set(eventType, handlers.filter(h => h !== handler))
    }
  }

  onAny(handler: EventHandler): void {
    this.allEventHandler.push(handler)
  }

  offAny(handler: EventHandler): void {
    this.allEventHandler = this.allEventHandler.filter(h => h !== handler)
  }

  private dispatchEvent(event: SSEEvent): void {
    const handlers = this.eventHandlers.get(event.type) || []
    handlers.forEach(handler => handler(event))

    this.allEventHandler.forEach(handler => handler(event))
  }
}

export const sseClient = new SSEClient()
