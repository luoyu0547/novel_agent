<script setup lang="ts">
import { ref, computed } from 'vue'
import { getRunSources } from '@/api/writingStudio'
import type { StudioSource } from '@/types/writingStudio'

const props = defineProps<{
  writingRunId: number
  novelId: number
  messageId: number
}>()

const emit = defineEmits<{
  'open-sources': [writingRunId: number]
}>()

const expanded = ref(false)
const loading = ref(false)
const sources = ref<StudioSource[]>([])
const loaded = ref(false)
const error = ref<string | null>(null)
const diagnosticsOpen = ref(false)

// Cache key — only load once per run
const cacheKey = computed(() => props.writingRunId)

async function toggleSources() {
  if (expanded.value) {
    expanded.value = false
    return
  }

  expanded.value = true

  // Load sources on first expansion
  if (!loaded.value) {
    loading.value = true
    error.value = null
    try {
      sources.value = await getRunSources(props.novelId, props.writingRunId)
      loaded.value = true
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载来源失败'
    } finally {
      loading.value = false
    }
  }

  emit('open-sources', props.writingRunId)
}
</script>

<template>
  <div class="studio-sources" :data-testid="`studio-sources-panel-${messageId}`">
    <el-button
      text
      size="small"
      :data-testid="`studio-sources-trigger-${messageId}`"
      @click="toggleSources"
    >
      {{ expanded ? '收起来源' : '查看来源' }}
    </el-button>

    <div v-if="expanded" class="studio-sources__content">
      <!-- Loading state -->
      <div v-if="loading" class="studio-sources__loading">
        <span class="studio-sources__spinner" />
        <span>加载中...</span>
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="studio-sources__error">
        {{ error }}
      </div>

      <!-- Source items -->
      <div v-else-if="sources.length > 0" class="studio-sources__list">
        <div
          v-for="source in sources"
          :key="source.id"
          class="studio-sources__item"
          :data-testid="`studio-source-${source.id}`"
        >
          <div class="studio-sources__item-title">{{ source.title }}</div>
          <div class="studio-sources__item-preview">{{ source.preview }}</div>
          <div class="studio-sources__item-reason">{{ source.inclusion_reason }}</div>

          <!-- Diagnostics behind a collapsible section -->
          <el-collapse v-if="source.diagnostics" class="studio-sources__diagnostics">
            <el-collapse-item title="检索诊断" :name="`diag-${source.id}`">
              <pre class="studio-sources__diag-content">{{ JSON.stringify(source.diagnostics, null, 2) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="studio-sources__empty">
        暂无来源信息
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio-sources {
  margin-top: $spacing-sm;

  &__content {
    margin-top: $spacing-xs;
  }

  &__loading {
    display: flex;
    align-items: center;
    gap: $spacing-xs;
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  &__spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid $color-border;
    border-top-color: $color-primary;
    border-radius: 50%;
    animation: sources-spin 0.8s linear infinite;
  }

  &__error {
    color: $color-error;
    font-size: $font-size-xs;
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: $spacing-sm;
  }

  &__item {
    padding: $spacing-xs $spacing-sm;
    background: $color-bg-secondary;
    border-radius: $radius-sm;
    border: 1px solid $color-border;

    &-title {
      font-size: $font-size-sm;
      font-weight: 600;
      color: $color-text;
      margin-bottom: 2px;
    }

    &-preview {
      font-size: $font-size-xs;
      color: $color-text-secondary;
      margin-bottom: 2px;
    }

    &-reason {
      font-size: $font-size-xs;
      color: $color-text-placeholder;
      font-style: italic;
    }
  }

  &__diagnostics {
    margin-top: $spacing-xs;
    border: none;

    :deep(.el-collapse-item__header) {
      font-size: $font-size-xs;
      color: $color-text-secondary;
      height: 24px;
      line-height: 24px;
    }
  }

  &__diag-content {
    font-size: $font-size-xs;
    color: $color-text-secondary;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
  }

  &__empty {
    color: $color-text-placeholder;
    font-size: $font-size-xs;
  }
}

@keyframes sources-spin {
  to { transform: rotate(360deg); }
}
</style>
