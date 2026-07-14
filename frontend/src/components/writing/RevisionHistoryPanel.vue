<script setup lang="ts">
import { computed } from 'vue'
import type { DraftRevision } from '@/types/revision'

const props = defineProps<{
  revisions: DraftRevision[]
}>()

const appliedRevisions = computed(() =>
  props.revisions.filter(r => r.status === 'applied'),
)

const rejectedRevisions = computed(() =>
  props.revisions.filter(r => r.status === 'rejected'),
)

const supersededRevisions = computed(() =>
  props.revisions.filter(r => r.status === 'superseded'),
)

const sourceTypeLabel: Record<string, string> = {
  planning_decision: '规划决策',
  review_issue: '审查问题',
  author_request: '作者请求',
  manual_edit: '手动编辑',
  restore: '恢复',
}

const statusTagType = (status: string) => {
  if (status === 'applied') return 'success'
  if (status === 'rejected') return 'danger'
  return 'info'
}
</script>

<template>
  <div class="revision-history-panel">
    <el-empty v-if="revisions.length === 0" description="暂无修订历史" />

    <template v-else>
      <!-- Applied revisions -->
      <div v-if="appliedRevisions.length" class="revision-history-panel__group">
        <p class="revision-history-panel__group-title">已应用</p>
        <div
          v-for="rev in appliedRevisions"
          :key="rev.id"
          class="revision-history-panel__item"
        >
          <div class="revision-history-panel__item-header">
            <span class="revision-history-panel__item-seq">R{{ rev.sequence }}</span>
            <el-tag size="small" :type="statusTagType(rev.status)">{{ sourceTypeLabel[rev.source_type] || rev.source_type }}</el-tag>
          </div>
          <p class="revision-history-panel__item-reason">{{ rev.reason }}</p>
        </div>
      </div>

      <!-- Rejected revisions -->
      <div v-if="rejectedRevisions.length" class="revision-history-panel__group">
        <p class="revision-history-panel__group-title">已拒绝</p>
        <div
          v-for="rev in rejectedRevisions"
          :key="rev.id"
          class="revision-history-panel__item revision-history-panel__item--rejected"
        >
          <div class="revision-history-panel__item-header">
            <span class="revision-history-panel__item-seq">R{{ rev.sequence }}</span>
            <el-tag size="small" :type="statusTagType(rev.status)">{{ sourceTypeLabel[rev.source_type] || rev.source_type }}</el-tag>
          </div>
          <p class="revision-history-panel__item-reason">{{ rev.reason }}</p>
        </div>
      </div>

      <!-- Superseded revisions -->
      <div v-if="supersededRevisions.length" class="revision-history-panel__group">
        <p class="revision-history-panel__group-title">已替代</p>
        <div
          v-for="rev in supersededRevisions"
          :key="rev.id"
          class="revision-history-panel__item revision-history-panel__item--superseded"
        >
          <div class="revision-history-panel__item-header">
            <span class="revision-history-panel__item-seq">R{{ rev.sequence }}</span>
            <el-tag size="small" :type="statusTagType(rev.status)">{{ sourceTypeLabel[rev.source_type] || rev.source_type }}</el-tag>
          </div>
          <p class="revision-history-panel__item-reason">{{ rev.reason }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.revision-history-panel__group {
  margin-bottom: 12px;
}

.revision-history-panel__group-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin: 0 0 4px;
}

.revision-history-panel__item {
  padding: 8px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  margin-bottom: 4px;

  &--rejected {
    opacity: 0.6;
  }

  &--superseded {
    opacity: 0.4;
  }
}

.revision-history-panel__item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.revision-history-panel__item-seq {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.revision-history-panel__item-reason {
  font-size: 12px;
  color: #909399;
  margin: 0;
}
</style>
