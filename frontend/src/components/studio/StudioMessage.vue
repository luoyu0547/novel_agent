<script setup lang="ts">
import { computed } from 'vue'
import type { WritingMessage, StudioConfirmationAction } from '@/types/writingStudio'
import StudioActionCard from './StudioActionCard.vue'
import StudioSourcesPanel from './StudioSourcesPanel.vue'

const props = defineProps<{
  message: WritingMessage
  novelId: number
}>()

const emit = defineEmits<{
  'confirm-action': [messageId: number, action: StudioConfirmationAction, payload: Record<string, unknown>]
  'open-sources': [writingRunId: number]
  'retry-message': [messageId: number]
}>()

// Extract display text from content_json based on message_type
const displayText = computed<string>(() => {
  const content = props.message.content_json
  if (!content) return ''
  // Most message types store text in content_json.text
  if (typeof content.text === 'string') return content.text
  // Draft messages may store content in content_json.content
  if (typeof content.content === 'string') return content.content
  // Fallback: stringify if it's a simple object
  return ''
})

// Message type label for visual distinction
const typeLabel = computed<string>(() => {
  const labels: Record<string, string> = {
    text: '',
    plan: '计划',
    brief: '简报',
    context: '上下文',
    draft: '草稿',
    review: '审阅',
    revision: '修订',
    sources: '来源',
    decision: '决策',
    error: '错误',
  }
  return labels[props.message.message_type] || ''
})

// CSS class based on role and type
const roleClass = computed(() => `studio-msg--${props.message.role}`)
const typeClass = computed(() => `studio-msg--type-${props.message.message_type}`)

// Whether this message needs confirmation action
const needsConfirmation = computed(() => props.message.action_status === 'needs_confirmation')
const isRunning = computed(() => props.message.action_status === 'running')
const isFailed = computed(() => props.message.action_status === 'failed')

// Whether to show the sources panel trigger (only for messages with writing_run_id)
const hasRunId = computed(() => props.message.writing_run_id != null)

// Whether to show the type badge (hide for plain text)
const showTypeBadge = computed(() => props.message.message_type !== 'text' && typeLabel.value !== '')

function handleConfirmAction(messageId: number, action: StudioConfirmationAction, payload: Record<string, unknown>) {
  emit('confirm-action', messageId, action, payload)
}

function handleOpenSources(writingRunId: number) {
  emit('open-sources', writingRunId)
}

function handleRetry() {
  emit('retry-message', props.message.id)
}
</script>

<template>
  <div
    class="studio-msg"
    :class="[roleClass, typeClass]"
    :data-testid="`studio-message-${message.id}`"
  >
    <!-- Role indicator -->
    <div class="studio-msg__role">
      <span v-if="message.role === 'assistant'" class="studio-msg__avatar studio-msg__avatar--assistant">AI</span>
      <span v-else-if="message.role === 'system'" class="studio-msg__avatar studio-msg__avatar--system">SYS</span>
    </div>

    <!-- Message body -->
    <div class="studio-msg__body">
      <!-- Type badge -->
      <el-tag
        v-if="showTypeBadge"
        size="small"
        :type="message.message_type === 'error' ? 'danger' : 'info'"
        class="studio-msg__type-badge"
      >
        {{ typeLabel }}
      </el-tag>

      <!-- Text content -->
      <div v-if="displayText" class="studio-msg__text">{{ displayText }}</div>

      <!-- Running indicator -->
      <div v-if="isRunning" class="studio-msg__running">
        <span class="studio-msg__spinner" />
        <span>正在生成...</span>
      </div>

      <!-- Error state with retry -->
      <div v-if="isFailed" class="studio-msg__error">
        <span>生成失败</span>
        <el-button size="small" text data-testid="studio-retry-btn" @click="handleRetry">
          重试
        </el-button>
      </div>

      <!-- Action card for needs_confirmation -->
      <StudioActionCard
        v-if="needsConfirmation"
        :message="message"
        @confirm-action="handleConfirmAction"
      />

      <!-- Sources panel trigger -->
      <StudioSourcesPanel
        v-if="hasRunId"
        :writing-run-id="message.writing_run_id!"
        :novel-id="novelId"
        :message-id="message.id"
        @open-sources="handleOpenSources"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio-msg {
  display: flex;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;

  &--assistant {
    // Assistant messages: default styling
  }

  &--author {
    // Author messages: slightly different alignment feel handled by avatar
  }

  &--system {
    opacity: 0.8;
  }

  &__role {
    flex-shrink: 0;
    width: 28px;
  }

  &__avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: $radius-sm;
    font-size: $font-size-xs;
    font-weight: 600;

    &--assistant {
      background: $color-primary-light;
      color: $color-primary-dark;
    }

    &--system {
      background: $color-bg-secondary;
      color: $color-text-secondary;
    }
  }

  &__body {
    flex: 1;
    min-width: 0;
  }

  &__type-badge {
    margin-bottom: $spacing-xs;
  }

  &__text {
    font-size: $font-size-sm;
    line-height: 1.7;
    color: $color-text;
    white-space: pre-wrap;
    word-break: break-word;
  }

  &__running {
    display: flex;
    align-items: center;
    gap: $spacing-xs;
    color: $color-text-secondary;
    font-size: $font-size-sm;
  }

  &__spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid $color-border;
    border-top-color: $color-primary;
    border-radius: 50%;
    animation: studio-spin 0.8s linear infinite;
  }

  &__error {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    color: $color-error;
    font-size: $font-size-sm;
  }
}

@keyframes studio-spin {
  to { transform: rotate(360deg); }
}
</style>
