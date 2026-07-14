<script setup lang="ts">
import { computed } from 'vue'
import type { ReviewIssue, RepairOption } from '@/types/revision'

const props = defineProps<{
  issues: ReviewIssue[]
  selectedIssueId: number | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'generate-options': [issueId: number]
  'create-candidate': [issueId: number]
  'ignore': [issueId: number]
}>()

const severityOrder: Record<string, number> = { blocking: 0, major: 1, minor: 2 }

const groupedIssues = computed(() => {
  const open = props.issues.filter(i => i.status === 'open')
  return [...open].sort((a, b) =>
    (severityOrder[a.severity] ?? 9) - (severityOrder[b.severity] ?? 9),
  )
})

const severityTagType = (severity: string) => {
  if (severity === 'blocking') return 'danger'
  if (severity === 'major') return 'warning'
  return 'info'
}

const resolutionModeLabel = (mode: string) => {
  if (mode === 'auto_fixable') return '自动修复'
  return '需要意图'
}

function handleGenerateOptions(issueId: number) {
  emit('generate-options', issueId)
}

function handleCreateCandidate(issueId: number) {
  emit('create-candidate', issueId)
}

function handleIgnore(issueId: number) {
  emit('ignore', issueId)
}

function getOptions(issue: ReviewIssue): RepairOption[] {
  return issue.repair_options_json ?? []
}
</script>

<template>
  <div class="review-issue-panel">
    <el-empty v-if="groupedIssues.length === 0" description="没有待处理的审查问题" />

    <div
      v-for="issue in groupedIssues"
      :key="issue.id"
      class="review-issue-panel__item"
      :class="{ 'review-issue-panel__item--selected': selectedIssueId === issue.id }"
      @click="$emit('generate-options', issue.id)"
    >
      <div class="review-issue-panel__header">
        <el-tag size="small" :type="severityTagType(issue.severity)">
          {{ issue.severity === 'blocking' ? '阻断' : issue.severity === 'major' ? '重要' : '轻微' }}
        </el-tag>
        <el-tag size="small" type="info">{{ resolutionModeLabel(issue.resolution_mode) }}</el-tag>
        <span class="review-issue-panel__type">{{ issue.issue_type }}</span>
      </div>

      <div class="review-issue-panel__body">
        <p class="review-issue-panel__description">{{ issue.description }}</p>
        <p v-if="issue.location" class="review-issue-panel__location">位置：{{ issue.location }}</p>
        <p v-if="issue.suggestion" class="review-issue-panel__suggestion">建议：{{ issue.suggestion }}</p>
      </div>

      <div v-if="selectedIssueId === issue.id && getOptions(issue).length > 0" class="review-issue-panel__options">
        <p class="review-issue-panel__section-title">修复方案</p>
        <div
          v-for="(opt, idx) in getOptions(issue)"
          :key="idx"
          class="review-issue-panel__option"
        >
          <div class="review-issue-panel__option-header">
            <span class="review-issue-panel__option-label">{{ opt.label }}</span>
            <el-tag v-if="opt.recommended" size="small" type="success">推荐</el-tag>
          </div>
          <p class="review-issue-panel__option-summary">{{ opt.summary }}</p>
          <p class="review-issue-panel__option-effect">预期效果：{{ opt.expected_effect }}</p>
        </div>
      </div>

      <div v-if="selectedIssueId === issue.id" class="review-issue-panel__actions">
        <el-button
          v-if="getOptions(issue).length === 0"
          size="small"
          type="primary"
          :loading="false"
          :disabled="disabled"
          @click.stop="handleGenerateOptions(issue.id)"
        >
          生成修复方案
        </el-button>
        <el-button
          v-if="getOptions(issue).length > 0"
          size="small"
          type="primary"
          :disabled="disabled"
          @click.stop="handleCreateCandidate(issue.id)"
        >
          创建候选修订
        </el-button>
        <el-button
          size="small"
          :disabled="disabled"
          @click.stop="handleIgnore(issue.id)"
        >
          忽略
        </el-button>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.review-issue-panel__item {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.2s;

  &--selected {
    border-color: #409eff;
    background: #f0f7ff;
  }
}

.review-issue-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.review-issue-panel__type {
  font-size: 13px;
  color: #606266;
}

.review-issue-panel__body {
  margin-bottom: 8px;
}

.review-issue-panel__description {
  font-size: 14px;
  color: #303133;
  margin: 0 0 4px;
}

.review-issue-panel__location,
.review-issue-panel__suggestion {
  font-size: 12px;
  color: #909399;
  margin: 2px 0;
}

.review-issue-panel__section-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin: 8px 0 4px;
}

.review-issue-panel__option {
  padding: 8px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 4px;
}

.review-issue-panel__option-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.review-issue-panel__option-label {
  font-size: 13px;
  font-weight: 500;
}

.review-issue-panel__option-summary,
.review-issue-panel__option-effect {
  font-size: 12px;
  color: #606266;
  margin: 2px 0;
}

.review-issue-panel__actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
