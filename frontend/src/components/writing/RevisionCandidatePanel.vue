<script setup lang="ts">
import { computed } from 'vue'
import type { DraftRevision, RevisionPatch } from '@/types/revision'

const props = defineProps<{
  candidate: DraftRevision | null
}>()

const emit = defineEmits<{
  apply: [revisionId: number]
  reject: [revisionId: number]
}>()

const sourceTypeLabel: Record<string, string> = {
  planning_decision: '规划决策',
  review_issue: '审查问题',
  author_request: '作者请求',
  manual_edit: '手动编辑',
  restore: '恢复',
}

const patches = computed<RevisionPatch[]>(() => {
  if (!props.candidate) return []
  return props.candidate.patches_json ?? []
})

async function handleApply() {
  if (!props.candidate) return

  if (props.candidate.expanded_scope) {
    try {
      await ElMessageBox.confirm(
        props.candidate.expanded_scope_reason || '此修订的影响范围超出了原始问题区域，确认应用？',
        '范围扩展确认',
        { confirmButtonText: '确认应用', cancelButtonText: '取消', type: 'warning' },
      )
      emit('apply', props.candidate.id)
    } catch {
      // User cancelled
    }
  } else {
    emit('apply', props.candidate.id)
  }
}

function handleReject() {
  if (!props.candidate) return
  emit('reject', props.candidate.id)
}
</script>

<template>
  <div v-if="candidate" class="revision-candidate-panel">
    <div class="revision-candidate-panel__header">
      <span class="revision-candidate-panel__label">候选修订</span>
      <el-tag size="small" type="warning">{{ sourceTypeLabel[candidate.source_type] || candidate.source_type }}</el-tag>
      <el-tag size="small">{{ candidate.status }}</el-tag>
    </div>

    <div class="revision-candidate-panel__meta">
      <p class="revision-candidate-panel__reason">原因：{{ candidate.reason }}</p>
      <p class="revision-candidate-panel__base">基准修订序列：R{{ candidate.base_revision_sequence }}</p>
    </div>

    <el-alert
      v-if="candidate.expanded_scope"
      type="warning"
      :closable="false"
      show-icon
      data-testid="expanded-scope-warning"
      class="revision-candidate-panel__scope-warning"
    >
      <template #title>
        范围扩展警告
      </template>
      {{ candidate.expanded_scope_reason || '此修订的影响范围超出了原始问题区域' }}
    </el-alert>

    <div v-if="patches.length > 0" class="revision-candidate-panel__patches">
      <p class="revision-candidate-panel__section-title">补丁详情</p>
      <div
        v-for="(patch, idx) in patches"
        :key="idx"
        class="revision-candidate-panel__patch"
      >
        <p class="revision-candidate-panel__patch-reason">{{ patch.reason }}</p>
        <div class="revision-candidate-panel__patch-diff">
          <div class="revision-candidate-panel__patch-old">
            <span class="revision-candidate-panel__patch-label">删除：</span>
            <span class="revision-candidate-panel__patch-text revision-candidate-panel__patch-text--deleted">{{ patch.original_text }}</span>
          </div>
          <div class="revision-candidate-panel__patch-new">
            <span class="revision-candidate-panel__patch-label">添加：</span>
            <span class="revision-candidate-panel__patch-text revision-candidate-panel__patch-text--added">{{ patch.replacement_text }}</span>
          </div>
        </div>
        <p class="revision-candidate-panel__patch-location">
          位置：{{ patch.start_offset }}-{{ patch.end_offset }}
        </p>
      </div>
    </div>

    <div v-if="patches.length === 0 && candidate.candidate_content" class="revision-candidate-panel__full-content">
      <p class="revision-candidate-panel__section-title">候选内容预览</p>
      <pre class="revision-candidate-panel__content-preview">{{ candidate.candidate_content.slice(0, 500) }}{{ candidate.candidate_content.length > 500 ? '...' : '' }}</pre>
    </div>

    <div class="revision-candidate-panel__actions">
      <el-button type="primary" size="small" data-testid="apply-candidate-btn" @click="handleApply">
        应用
      </el-button>
      <el-button size="small" data-testid="reject-candidate-btn" @click="handleReject">
        拒绝
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.revision-candidate-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.revision-candidate-panel__label {
  font-weight: 600;
  font-size: 15px;
}

.revision-candidate-panel__meta {
  margin-bottom: 12px;
}

.revision-candidate-panel__reason,
.revision-candidate-panel__base {
  font-size: 13px;
  color: #606266;
  margin: 4px 0;
}

.revision-candidate-panel__scope-warning {
  margin-bottom: 12px;
}

.revision-candidate-panel__section-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin: 8px 0 4px;
}

.revision-candidate-panel__patch {
  padding: 8px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 8px;
}

.revision-candidate-panel__patch-reason {
  font-size: 12px;
  color: #909399;
  margin: 0 0 4px;
}

.revision-candidate-panel__patch-diff {
  margin: 4px 0;
}

.revision-candidate-panel__patch-old,
.revision-candidate-panel__patch-new {
  font-size: 13px;
  margin: 2px 0;
}

.revision-candidate-panel__patch-label {
  font-weight: 500;
  color: #606266;
}

.revision-candidate-panel__patch-text {
  font-family: monospace;
  font-size: 12px;
}

.revision-candidate-panel__patch-text--deleted {
  color: #f56c6c;
  text-decoration: line-through;
}

.revision-candidate-panel__patch-text--added {
  color: #67c23a;
}

.revision-candidate-panel__patch-location {
  font-size: 11px;
  color: #c0c4cc;
  margin: 4px 0 0;
}

.revision-candidate-panel__content-preview {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
}

.revision-candidate-panel__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
</style>
