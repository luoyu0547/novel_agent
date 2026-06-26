<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'
import type { ChapterStatus } from '@/types'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()

const novelId = computed(() => Number(route.params.id))
const chapterId = computed(() => Number(route.params.chapterId))
const title = ref(''); const content = ref(''); const saving = ref(false)
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
  } finally { saving.value = false }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave() }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>
<template>
  <div class="editor">
    <header class="editor__header">
      <button class="editor__back" @click="router.push(`/novels/${novelId}`)">← 返回</button>
      <span class="editor__novel-name">{{ novelStore.currentNovel?.title || '' }}</span>
      <div class="editor__actions">
        <select v-model="status" class="editor__status">
          <option value="draft">草稿</option>
          <option value="reviewed">已确认</option>
          <option value="locked">锁定</option>
        </select>
        <AppButton size="sm" :loading="saving" @click="handleSave">保存</AppButton>
      </div>
    </header>
    <div class="editor__body">
      <AppInput v-model="title" placeholder="章节标题" size="lg" class="editor__title-input" />
      <AppTextarea v-model="content" placeholder="开始写作..." class="editor__content" :rows="1" />
      <section class="editor__summary">
        <h3 class="editor__summary-title">章节摘要</h3>
        <AppTextarea v-model="summary" placeholder="手动记录本章关键事实、角色变化和后续需要记住的信息" :rows="5" />
      </section>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.editor { min-height: 100vh; display: flex; flex-direction: column; background: $color-bg-card;
  &__header { display: flex; align-items: center; justify-content: space-between; padding: $spacing-md $spacing-lg; border-bottom: 1px solid $color-border; }
  &__back { font-size: $font-size-sm; color: $color-text-secondary; transition: color $transition-fast; &:hover { color: $color-primary-dark; } }
  &__novel-name { font-size: $font-size-sm; color: $color-text-secondary; }
  &__actions { display: flex; align-items: center; gap: $spacing-sm; }
  &__status { border: 1px solid $color-border; border-radius: $radius-md; padding: 4px 8px; background: $color-bg-card; color: $color-text; }
  &__body { max-width: 800px; width: 100%; margin: 0 auto; padding: $spacing-xl $spacing-lg; flex: 1; display: flex; flex-direction: column; gap: $spacing-lg; }
  &__title-input { :deep(input) { font-size: $font-size-xl; font-weight: 700; border: none; padding: 0; &:focus { box-shadow: none; } } }
  &__content { flex: 1; :deep(textarea) { height: 100%; min-height: 60vh; border: none; padding: 0; font-size: $font-size-md; line-height: 2; resize: none; &:focus { box-shadow: none; } } }
  &__summary { border-top: 1px solid $color-border; padding-top: $spacing-lg; }
  &__summary-title { font-size: $font-size-md; font-weight: 600; margin-bottom: $spacing-sm; } }
</style>
