import client from './client'
import type { PendingMemory, ExtractRequest, ExtractResponse } from '@/types'

export function extractChapter(
  novelId: number,
  chapterId: number,
  mode: 'standard' | 'deep' = 'standard',
): Promise<ExtractResponse> {
  return client.post(`/novels/${novelId}/chapters/${chapterId}/extract`, { mode } as ExtractRequest)
}

export function listPendingMemories(novelId: number): Promise<PendingMemory[]> {
  return client.get(`/novels/${novelId}/pending-memories`)
}

export function confirmPendingMemory(novelId: number, memoryId: number): Promise<void> {
  return client.put(`/novels/${novelId}/pending-memories/${memoryId}/confirm`)
}

export function rejectPendingMemory(novelId: number, memoryId: number): Promise<void> {
  return client.put(`/novels/${novelId}/pending-memories/${memoryId}/reject`)
}

export function batchPendingMemories(
  novelId: number,
  ids: number[],
  action: 'confirm' | 'reject',
): Promise<void> {
  return client.put(`/novels/${novelId}/pending-memories/batch`, { ids, action })
}
