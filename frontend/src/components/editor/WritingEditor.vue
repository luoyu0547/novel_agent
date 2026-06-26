<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { ChapterStatus } from '@/types'
import { CHAPTER_STATUS_OPTIONS } from '@/constants/options'

const router = useRouter()
const route = useRoute()

const props = defineProps<{
  title: string
  content: string
  status: ChapterStatus
  saving: boolean
  savedAt: string | null
}>()

const emit = defineEmits<{
  'update:title': [value: string]
  'update:content': [value: string]
  'update:status': [value: ChapterStatus]
  save: []
}>()

const wordCount = computed(() => props.content.length)

const debounceTimer = ref<ReturnType<typeof setTimeout> | null>(null)
function onContentInput(value: string) {
  emit('update:content', value)
  if (debounceTimer.value) clearTimeout(debounceTimer.value)
  debounceTimer.value = setTimeout(() => emit('save'), 3000)
}

function onManualSave() {
  if (debounceTimer.value) clearTimeout(debounceTimer.value)
  emit('save')
}

const focused = ref(false)
defineExpose({ wordCount })
</script>

<template>
  <div class="writing-editor">
    <header class="writing-editor__header">
      <el-button text @click="router.back()">← 返回</el-button>
      <span class="writing-editor__novel-name">{{ route.params.id }}</span>
      <div class="writing-editor__actions">
        <el-select :model-value="status" size="small" @update:model-value="emit('update:status', $event)">
          <el-option
            v-for="opt in CHAPTER_STATUS_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-text size="small" type="info">已写 {{ wordCount }} 字</el-text>
        <el-text v-if="saving" size="small" type="info">保存中…</el-text>
        <el-text v-else-if="savedAt" size="small" type="info">已保存 {{ savedAt }}</el-text>
        <el-button size="small" type="primary" :loading="saving" @click="onManualSave">保存</el-button>
        <el-button size="small" text @click="focused = !focused">{{ focused ? '退出专注' : '专注' }}</el-button>
      </div>
    </header>
    <div class="writing-editor__body" :class="{ 'writing-editor__body--focused': focused }">
      <el-input
        :model-value="title"
        placeholder="章节标题"
        class="writing-editor__title-input"
        @update:model-value="emit('update:title', $event)"
      />
      <el-input
        :model-value="content"
        type="textarea"
        :autosize="{ minRows: 20 }"
        placeholder="开始写作..."
        class="writing-editor__content"
        @update:model-value="onContentInput"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.writing-editor {
  min-height: 100vh; display: flex; flex-direction: column; background: $color-bg-card;
  &__header { display: flex; align-items: center; justify-content: space-between; padding: $spacing-md $spacing-lg; border-bottom: 1px solid $color-border; }
  &__novel-name { font-size: $font-size-sm; color: $color-text-secondary; }
  &__actions { display: flex; align-items: center; gap: $spacing-sm; }
  &__body { max-width: 760px; width: 100%; margin: 0 auto; padding: $spacing-xl $spacing-lg; flex: 1; display: flex; flex-direction: column; gap: $spacing-lg;
    &--focused {
      .writing-editor__header { opacity: 0.15; transition: opacity 0.3s; &:hover { opacity: 1; } }
    }
  }
  &__title-input { :deep(.el-input__wrapper) { box-shadow: none !important; padding: 0;
    .el-input__inner { font-size: $font-size-xl; font-weight: 700; } } }
  &__content { flex: 1;
    :deep(.el-textarea__inner) {
      min-height: 60vh; border: none; padding: 0; font-size: $font-size-md; line-height: 2; resize: none;
      font-family: $font-family-serif; color: $color-text; background: transparent;
      &:focus { box-shadow: none; }
    }
  }
}
</style>
