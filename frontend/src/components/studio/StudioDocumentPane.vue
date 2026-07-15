<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import type { StudioDocument } from '@/types/writingStudio'

type SaveState = 'idle' | 'saving' | 'saved' | 'conflict' | 'error'

const props = defineProps<{
  document: StudioDocument | null
  saveState: SaveState
}>()

const emit = defineEmits<{
  'update:title': [value: string]
  'update:content': [value: string]
  'save-working-copy': [payload: { title: string; content: string; baseRevisionSequence: number }]
  accept: []
  discard: []
  'open-version-inspector': []
}>()

// Local editor state — synced from props but edited locally
const title = ref('')
const content = ref('')

// Debounce timer for draft saves
let saveTimer: ReturnType<typeof setTimeout> | null = null

// Sync from props to local state whenever the document changes
watch(
  () => props.document,
  (value) => {
    title.value = value?.title ?? ''
    content.value = value?.content ?? ''
  },
  { immediate: true, deep: true },
)

// Clear timer on unmount
onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
})

// Save status label
const saveStatusLabel = ref<string>('')

watch(
  () => props.saveState,
  (state: SaveState) => {
    switch (state) {
      case 'saving':
        saveStatusLabel.value = '保存中…'
        break
      case 'saved':
        saveStatusLabel.value = '已保存'
        break
      case 'error':
        saveStatusLabel.value = '保存失败'
        break
      case 'conflict':
        saveStatusLabel.value = '版本冲突'
        break
      default:
        saveStatusLabel.value = ''
    }
  },
  { immediate: true },
)

// Save status CSS class
const saveStatusClass = ref<string>('')

watch(
  () => props.saveState,
  (state: SaveState) => {
    switch (state) {
      case 'saving':
        saveStatusClass.value = 'studio-doc__status--saving'
        break
      case 'saved':
        saveStatusClass.value = 'studio-doc__status--saved'
        break
      case 'error':
        saveStatusClass.value = 'studio-doc__status--error'
        break
      case 'conflict':
        saveStatusClass.value = 'studio-doc__status--conflict'
        break
      default:
        saveStatusClass.value = ''
    }
  },
  { immediate: true },
)

const isDraft = ref(false)

watch(
  () => props.document?.kind,
  (kind) => {
    isDraft.value = kind === 'draft'
  },
  { immediate: true },
)

// Schedule a debounced save for draft documents (800ms)
function scheduleDraftSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    if (props.document) {
      emit('save-working-copy', {
        title: title.value,
        content: content.value,
        baseRevisionSequence: props.document.baseRevisionSequence,
      })
    }
  }, 800)
}

// Handle title input
function onTitleInput(value: string) {
  title.value = value
  emit('update:title', value)
  if (isDraft.value) {
    scheduleDraftSave()
  }
}

// Handle content input
function onContentInput(value: string) {
  content.value = value
  emit('update:content', value)
  if (isDraft.value) {
    scheduleDraftSave()
  }
}

// Accept draft
function handleAccept() {
  emit('accept')
}

// Discard draft
function handleDiscard() {
  emit('discard')
}

// Open version inspector
function handleOpenVersionInspector() {
  emit('open-version-inspector')
}
</script>

<template>
  <div v-if="document" class="studio-doc" data-testid="studio-document-pane">
    <!-- Save status bar -->
    <div class="studio-doc__status-bar">
      <div class="studio-doc__status-left">
        <span
          v-if="saveStatusLabel"
          class="studio-doc__status"
          :class="saveStatusClass"
          data-testid="studio-save-status"
        >{{ saveStatusLabel }}</span>
      </div>
      <div class="studio-doc__status-right">
        <el-button
          v-if="isDraft"
          size="small"
          text
          data-testid="studio-version-inspector-btn"
          @click="handleOpenVersionInspector"
        >
          版本
        </el-button>
        <template v-if="isDraft">
          <el-button
            size="small"
            type="primary"
            data-testid="studio-accept-btn"
            @click="handleAccept"
          >
            采纳
          </el-button>
          <el-button
            size="small"
            data-testid="studio-discard-btn"
            @click="handleDiscard"
          >
            丢弃
          </el-button>
        </template>
      </div>
    </div>

    <!-- Title input -->
    <div class="studio-doc__title-area">
      <el-input
        :model-value="title"
        placeholder="章节标题"
        class="studio-doc__title-input"
        data-testid="studio-document-title"
        @update:model-value="onTitleInput"
      />
    </div>

    <!-- Content textarea -->
    <div class="studio-doc__content-area">
      <el-input
        :model-value="content"
        type="textarea"
        :autosize="{ minRows: 20 }"
        placeholder="开始写作..."
        class="studio-doc__textarea"
        data-testid="studio-document-content"
        @update:model-value="onContentInput"
      />
    </div>
  </div>

  <!-- Empty state when no document selected -->
  <div v-else class="studio-doc__empty" data-testid="studio-document-empty">
    <p>选择章节或草稿开始创作</p>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio-doc {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: $color-bg-card;

  &__status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $spacing-sm $spacing-md;
    border-bottom: 1px solid $color-border;
    flex-shrink: 0;
  }

  &__status-left {
    display: flex;
    align-items: center;
  }

  &__status-right {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
  }

  &__status {
    font-size: $font-size-xs;
    font-weight: 500;

    &--saving {
      color: $color-text-secondary;
    }

    &--saved {
      color: $color-success;
    }

    &--error {
      color: $color-error;
    }

    &--conflict {
      color: $color-warning;
    }
  }

  &__title-area {
    padding: $spacing-md $spacing-lg 0;
    flex-shrink: 0;
  }

  &__title-input {
    :deep(.el-input__wrapper) {
      box-shadow: none !important;
      padding: 0;

      .el-input__inner {
        font-size: $font-size-xl;
        font-weight: 700;
        color: $color-text;
      }
    }
  }

  &__content-area {
    flex: 1;
    padding: $spacing-md $spacing-lg $spacing-xl;
    overflow-y: auto;
  }

  &__textarea {
    flex: 1;

    :deep(.el-textarea__inner) {
      min-height: 60vh;
      border: none;
      padding: 0;
      font-size: $font-size-md;
      line-height: 2;
      resize: none;
      font-family: $font-family-serif;
      color: $color-text;
      background: transparent;

      &:focus {
        box-shadow: none;
      }
    }
  }

  &__empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: $color-text-placeholder;
    font-size: $font-size-sm;
  }
}
</style>
