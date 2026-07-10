<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import { useWritingStore } from '@/stores/writing'
import WritingEditor from '@/components/editor/WritingEditor.vue'
import type { ChapterStatus } from '@/types'

const route = useRoute(); const novelStore = useNovelStore(); const writingStore = useWritingStore()
const novelId = computed(() => Number(route.params.id))
const chapterId = computed(() => Number(route.params.chapterId))
const title = ref(''); const content = ref(''); const saving = ref(false); const savedAt = ref<string | null>(null)
const summary = ref('')
const status = ref<ChapterStatus>('draft')

const isLocked = computed(() => status.value === 'locked')

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await novelStore.loadChapter(novelId.value, chapterId.value)
  if (novelStore.currentChapter) {
    title.value = novelStore.currentChapter.title
    content.value = novelStore.currentChapter.content
    summary.value = novelStore.currentChapter.summary
    status.value = novelStore.currentChapter.status
  }
  await writingStore.fetchWritingRuns(novelId.value)
  const lastRun = writingStore.writingRuns[0]
  if (lastRun && lastRun.status === 'completed') {
    await writingStore.fetchRepairs(novelId.value, lastRun.id)
  }
})

async function handleSave() {
  saving.value = true
  try {
    await novelStore.updateChapter(novelId.value, chapterId.value, {
      title: title.value,
      content: content.value,
      summary: summary.value,
      status: status.value,
    })
    savedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } finally { saving.value = false }
}

function handleResolveRepair(repairId: number, payload: { action: 'apply' | 'dismiss'; choice_index?: number; intent_text?: string }) {
  writingStore.resolveRepair(novelId.value, repairId, payload)
}

async function handlePublish() {
  saving.value = true
  try {
    const { publishChapter } = await import('@/api/writing')
    await publishChapter(novelId.value, chapterId.value)
    status.value = 'locked'
    ElMessage.success('章节已发布为锁定状态')
  } catch {
    ElMessage.error('发布失败')
  } finally {
    saving.value = false
  }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); if (!isLocked.value) handleSave() }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>
<template>
  <div class="editor-view">
    <WritingEditor
      :title="title"
      :content="content"
      :status="status"
      :saving="saving"
      :saved-at="savedAt"
      :repair-logs="writingStore.repairLogs"
      :pending-repairs="writingStore.pendingRepairs"
      @update:title="title = $event"
      @update:content="content = $event"
      @update:status="status = $event"
      @save="handleSave"
      @publish="handlePublish"
      @resolve="handleResolveRepair"
    />
  </div>
</template>
<style scoped lang="scss">
.editor-view { min-height: 100vh; }
</style>
