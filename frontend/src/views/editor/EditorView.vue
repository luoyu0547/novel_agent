<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import WritingEditor from '@/components/editor/WritingEditor.vue'
import type { ChapterStatus } from '@/types'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()
const novelId = computed(() => Number(route.params.id))
const chapterId = computed(() => Number(route.params.chapterId))
const title = ref(''); const content = ref(''); const saving = ref(false); const savedAt = ref<string | null>(null)
const summary = ref('')
const status = ref<ChapterStatus>('draft')

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await novelStore.loadChapter(novelId.value, chapterId.value)
  if (novelStore.currentChapter) {
    title.value = novelStore.currentChapter.title
    content.value = novelStore.currentChapter.content
    summary.value = novelStore.currentChapter.summary
    status.value = novelStore.currentChapter.status
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

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave() }
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
      @update:title="title = $event"
      @update:content="content = $event"
      @update:status="status = $event"
      @save="handleSave"
    />
  </div>
</template>
<style scoped lang="scss">
.editor-view { min-height: 100vh; }
</style>
