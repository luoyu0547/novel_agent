<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RepairLog, PendingRepair } from '@/types/writing'

const props = defineProps<{
  repair: RepairLog | PendingRepair
  type: 'log' | 'pending'
}>()

const emit = defineEmits<{
  (e: 'resolve', repairId: number, payload: { action: 'apply' | 'dismiss'; choice_index?: number; intent_text?: string }): void
}>()

const isLog = computed(() => props.type === 'log')

const selectedOption = ref<number>()
const intentText = ref('')
const processing = ref(false)

const pending = computed(() => props.repair as PendingRepair)

const issueTypeLabels: Record<string, string> = {
  character_choice: '角色抉择',
  expression: '表达方式',
  direction: '创作方向',
  task_completion: '任务完成度',
  style: '风格',
  character: '人设',
  continuity: '连续性',
  world: '世界观',
  foreshadowing: '伏笔',
  length: '篇幅',
}

const issueTypeLabel = computed(() => issueTypeLabels[props.repair.issue_type] || props.repair.issue_type)

async function handleApply() {
  if (processing.value) return
  processing.value = true
  try {
    if (pending.value.intent_type === 'choice' && selectedOption.value !== undefined) {
      emit('resolve', pending.value.id, { action: 'apply', choice_index: selectedOption.value })
    } else if (pending.value.intent_type === 'freeform' && intentText.value.trim()) {
      emit('resolve', pending.value.id, { action: 'apply', intent_text: intentText.value.trim() })
    }
  } finally {
    processing.value = false
  }
}

async function handleDismiss() {
  if (processing.value) return
  processing.value = true
  try {
    emit('resolve', pending.value.id, { action: 'dismiss' })
  } finally {
    processing.value = false
  }
}
</script>

<template>
  <div v-if="isLog" class="repair-item repair-item--log">
    <div class="repair-item__header">
      <el-tag size="small" type="info">{{ issueTypeLabel }}</el-tag>
      <el-text size="small" type="info">{{ repair.description }}</el-text>
    </div>
  </div>

  <div v-else class="repair-item repair-item--pending">
    <div class="repair-item__header">
      <el-tag size="small" type="warning">{{ issueTypeLabel }}</el-tag>
      <el-text size="small" class="repair-item__desc">{{ pending.description }}</el-text>
    </div>

    <el-text size="small" type="info" class="repair-item__context">
      {{ pending.context.slice(0, 100) }}{{ pending.context.length > 100 ? '...' : '' }}
    </el-text>

    <div v-if="pending.intent_type === 'choice' && pending.options" class="repair-item__options">
      <el-radio-group v-model="selectedOption">
        <el-radio v-for="(opt, i) in pending.options" :key="i" :value="i" size="small">
          <div class="repair-item__option">
            <div class="repair-item__option-label">{{ opt.label }}</div>
            <div class="repair-item__option-summary">{{ opt.summary }}</div>
          </div>
        </el-radio>
      </el-radio-group>
    </div>

    <div v-else-if="pending.intent_type === 'freeform'" class="repair-item__intent">
      <el-input
        v-model="intentText"
        :rows="3"
        type="textarea"
        placeholder="描述你希望的方向..."
      />
    </div>

    <div class="repair-item__actions">
      <el-button size="small" @click="handleDismiss">忽略</el-button>
      <el-button
        size="small"
        type="primary"
        :disabled="(pending.intent_type === 'choice' && selectedOption === undefined) || (pending.intent_type === 'freeform' && !intentText.trim())"
        :loading="processing"
        @click="handleApply"
      >
        {{ pending.intent_type === 'choice' ? '应用选择' : '按意图修复' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.repair-item {
  padding: $spacing-sm;
  border-radius: $radius-md;
}

.repair-item--log {
  background: $color-bg-secondary;
}

.repair-item--pending {
  border: 1px solid $color-border;
  background: $color-bg-card;
}

.repair-item__header {
  display: flex;
  align-items: flex-start;
  gap: $spacing-sm;
  margin-bottom: $spacing-xs;
}

.repair-item__desc {
  flex: 1;
  line-height: 1.4;
}

.repair-item__context {
  display: block;
  padding: $spacing-xs $spacing-sm;
  background: $color-bg-secondary;
  border-radius: $radius-sm;
  margin-bottom: $spacing-sm;
  font-style: italic;
}

.repair-item__options {
  margin-bottom: $spacing-sm;
}

.repair-item__option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.repair-item__option-label {
  font-weight: 600;
  color: $color-text;
}

.repair-item__option-summary {
  font-size: 12px;
  color: $color-text-secondary;
}

.repair-item__intent {
  margin-bottom: $spacing-sm;
}

.repair-item__actions {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-sm;
}
</style>
