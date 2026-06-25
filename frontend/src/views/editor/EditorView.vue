<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()

const novelId = computed(() => Number(route.params.id))
const chapterId = computed(() => Number(route.params.chapterId))
const title = ref(''); const content = ref(''); const saving = ref(false)

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await novelStore.loadChapter(novelId.value, chapterId.value)
  if (novelStore.currentChapter) {
    title.value = novelStore.currentChapter.title
    content.value = novelStore.currentChapter.content
  }
})

async function handleSave() {
  saving.value = true
  try {
    await novelStore.updateChapter(novelId.value, chapterId.value, { title: title.value, content: content.value })
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
      <AppButton size="sm" :loading="saving" @click="handleSave">保存</AppButton>
    </header>
    <div class="editor__body">
      <AppInput v-model="title" placeholder="章节标题" size="lg" class="editor__title-input" />
      <AppTextarea v-model="content" placeholder="开始写作..." class="editor__content" :rows="1" />
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.editor { min-height: 100vh; display: flex; flex-direction: column; background: $color-bg-card;
  &__header { display: flex; align-items: center; justify-content: space-between; padding: $spacing-md $spacing-lg; border-bottom: 1px solid $color-border; }
  &__back { font-size: $font-size-sm; color: $color-text-secondary; transition: color $transition-fast; &:hover { color: $color-primary-dark; } }
  &__novel-name { font-size: $font-size-sm; color: $color-text-secondary; }
  &__body { max-width: 800px; width: 100%; margin: 0 auto; padding: $spacing-xl $spacing-lg; flex: 1; display: flex; flex-direction: column; gap: $spacing-lg; }
  &__title-input { :deep(input) { font-size: $font-size-xl; font-weight: 700; border: none; padding: 0; &:focus { box-shadow: none; } } }
  &__content { flex: 1; :deep(textarea) { height: 100%; min-height: 60vh; border: none; padding: 0; font-size: $font-size-md; line-height: 2; resize: none; &:focus { box-shadow: none; } } } }
</style>
