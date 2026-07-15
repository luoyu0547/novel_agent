import client from './client'
import type { StudioWorkspace, StudioMessageResult, StudioConfirmationAction, DraftWorkingCopy } from '@/types/writingStudio'

export function getStudioSession(novelId: number, sessionId: number): Promise<StudioWorkspace> {
  return client.get(`/novels/${novelId}/writing-sessions/${sessionId}`)
}

export function sendStudioMessage(
  novelId: number,
  sessionId: number,
  body: { text: string; idempotency_key: string },
): Promise<StudioMessageResult> {
  return client.post(`/novels/${novelId}/writing-sessions/${sessionId}/messages`, body)
}

export function confirmStudioAction(
  novelId: number,
  sessionId: number,
  messageId: number,
  body: { action: StudioConfirmationAction; payload: Record<string, unknown> },
): Promise<StudioMessageResult> {
  return client.post(`/novels/${novelId}/writing-sessions/${sessionId}/actions/${messageId}`, body)
}

export function saveStudioWorkingCopy(
  novelId: number,
  sessionId: number,
  body: { title: string; content: string; base_revision_sequence: number },
): Promise<DraftWorkingCopy> {
  return client.put(`/novels/${novelId}/writing-sessions/${sessionId}/working-copy`, body)
}
