<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import type { WritingMessage, StudioConfirmationAction } from '@/types/writingStudio'
import StudioMessage from './StudioMessage.vue'

const props = defineProps<{
  messages: WritingMessage[]
  novelId: number
  sending: boolean
}>()

const emit = defineEmits<{
  'send-message': [text: string]
  'confirm-action': [messageId: number, action: StudioConfirmationAction, payload: Record<string, unknown>]
  'open-sources': [writingRunId: number]
  'retry-message': [messageId: number]
}>()

const composer = ref('')
const messageList = ref<HTMLElement | null>(null)

// Auto-scroll to bottom when new messages arrive
watch(() => props.messages.length, async () => {
  await nextTick()
  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight
  }
})

async function submit() {
  const text = composer.value.trim()
  if (!text || props.sending) return
  emit('send-message', text)
  composer.value = ''
}

function handleConfirmAction(messageId: number, action: StudioConfirmationAction, payload: Record<string, unknown>) {
  emit('confirm-action', messageId, action, payload)
}

function handleOpenSources(writingRunId: number) {
  emit('open-sources', writingRunId)
}

function handleRetry(messageId: number) {
  emit('retry-message', messageId)
}
</script>

<template>
  <div class="studio-conversation" data-testid="studio-conversation-pane">
    <!-- Message timeline -->
    <div ref="messageList" class="studio-conversation__messages">
      <div v-if="messages.length === 0" class="studio-conversation__empty" data-testid="studio-conversation-empty">
        <p>开始与 AI 助手对话</p>
        <p class="studio-conversation__empty-hint">描述你的创作意图，AI 将协助你完成写作</p>
      </div>

      <StudioMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        :novel-id="novelId"
        @confirm-action="handleConfirmAction"
        @open-sources="handleOpenSources"
        @retry-message="handleRetry"
      />
    </div>

    <!-- Composer input -->
    <div class="studio-conversation__composer">
      <el-input
        v-model="composer"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 4 }"
        placeholder="输入创作指令..."
        :disabled="sending"
        data-testid="studio-composer-input"
        @keydown.enter.exact.prevent="submit"
      />
      <el-button
        type="primary"
        size="small"
        :disabled="!composer.trim() || sending"
        data-testid="studio-send-btn"
        @click="submit"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio-conversation {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__messages {
    flex: 1;
    overflow-y: auto;
    padding: $spacing-sm;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: $color-text-placeholder;
    text-align: center;

    p {
      margin: 0;
      font-size: $font-size-sm;
    }
  }

  &__empty-hint {
    font-size: $font-size-xs !important;
    margin-top: $spacing-xs !important;
  }

  &__composer {
    display: flex;
    gap: $spacing-sm;
    padding: $spacing-sm $spacing-md;
    border-top: 1px solid $color-border;
    background: $color-bg-card;
    flex-shrink: 0;
    align-items: flex-end;

    :deep(.el-textarea__inner) {
      font-size: $font-size-sm;
    }
  }
}
</style>
