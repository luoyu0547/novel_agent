import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PendingMemory } from '@/types'
import * as api from '@/api/pendingMemory'

export const usePendingMemoryStore = defineStore('pendingMemory', () => {
  const memories = ref<PendingMemory[]>([])
  const loading = ref(false)

  const pendingCount = () => memories.value.filter(m => m.status === 'pending').length

  async function fetchMemories(novelId: number) {
    loading.value = true
    try {
      memories.value = await api.listPendingMemories(novelId)
    } finally {
      loading.value = false
    }
  }

  async function confirm(memoryId: number) {
    const item = memories.value.find(m => m.id === memoryId)
    if (!item) return
    await api.confirmPendingMemory(item.novel_id, memoryId)
    item.status = 'confirmed'
  }

  async function reject(memoryId: number) {
    const item = memories.value.find(m => m.id === memoryId)
    if (!item) return
    await api.rejectPendingMemory(item.novel_id, memoryId)
    item.status = 'rejected'
  }

  async function batchAction(ids: number[], action: 'confirm' | 'reject') {
    if (!ids.length) return
    const novelId = memories.value.find(m => ids.includes(m.id))?.novel_id
    if (!novelId) return
    await api.batchPendingMemories(novelId, ids, action)
    memories.value.forEach(m => {
      if (ids.includes(m.id)) m.status = action === 'confirm' ? 'confirmed' : 'rejected'
    })
  }

  async function extract(novelId: number, chapterId: number, mode: 'standard' | 'deep' = 'standard') {
    return await api.extractChapter(novelId, chapterId, mode)
  }

  return { memories, loading, pendingCount, fetchMemories, confirm, reject, batchAction, extract }
})
