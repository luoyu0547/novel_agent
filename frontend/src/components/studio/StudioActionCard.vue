<script setup lang="ts">
import { computed } from 'vue'
import type { WritingMessage, StudioConfirmationAction } from '@/types/writingStudio'

const props = defineProps<{
  message: WritingMessage
}>()

const emit = defineEmits<{
  'confirm-action': [messageId: number, action: StudioConfirmationAction, payload: Record<string, unknown>]
}>()

// Extract available actions from content_json
const availableActions = computed(() => {
  const content = props.message.content_json
  if (!content || !Array.isArray(content.actions)) {
    // Default actions for needs_confirmation messages
    return ['accept', 'discard'] as StudioConfirmationAction[]
  }
  return content.actions as StudioConfirmationAction[]
})

// Action label mapping
const actionLabels: Record<string, string> = {
  accept: '采纳',
  discard: '丢弃',
  apply_revision: '应用修订',
  force_accept: '强制采纳',
  restore_version: '恢复版本',
}

// Action type mapping for button styling
const actionType: Record<string, string> = {
  accept: 'primary',
  discard: 'default',
  apply_revision: 'warning',
  force_accept: 'danger',
  restore_version: 'default',
}

function confirm(action: StudioConfirmationAction) {
  emit('confirm-action', props.message.id, action, {})
}
</script>

<template>
  <div class="studio-action" :data-testid="`studio-action-card-${message.id}`">
    <div class="studio-action__prompt">
      {{ message.content_json?.prompt || '请确认操作' }}
    </div>
    <div class="studio-action__buttons">
      <el-button
        v-for="action in availableActions"
        :key="action"
        size="small"
        :type="(actionType[action] as any) || 'default'"
        :data-testid="`studio-confirm-${action}`"
        @click="confirm(action)"
      >
        {{ actionLabels[action] || action }}
      </el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio-action {
  margin-top: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: $color-bg-secondary;
  border: 1px solid $color-border;
  border-radius: $radius-md;

  &__prompt {
    font-size: $font-size-sm;
    color: $color-text;
    margin-bottom: $spacing-sm;
  }

  &__buttons {
    display: flex;
    gap: $spacing-sm;
    flex-wrap: wrap;
  }
}
</style>
