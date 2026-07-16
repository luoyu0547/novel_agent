<script setup lang="ts">
import { ref } from 'vue'
import DraftVersionTimeline from '@/components/writing/DraftVersionTimeline.vue'
import RevisionHistoryPanel from '@/components/writing/RevisionHistoryPanel.vue'
import ReviewIssuePanel from '@/components/writing/ReviewIssuePanel.vue'
import RevisionCandidatePanel from '@/components/writing/RevisionCandidatePanel.vue'
import type { DraftVersion, DraftRevision, ReviewIssue } from '@/types/revision'

defineProps<{
  modelValue: boolean
  versions: DraftVersion[]
  currentVersion: DraftVersion | null
  revisions: DraftRevision[]
  issues: ReviewIssue[]
  candidate: DraftRevision | null
  selectedIssueId: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'create-version': [payload: { basedOnVersionId: number; changeReason: string }]
  'restore': [payload: { versionId: number; changeReason: string }]
  'select-version': [versionId: number]
  'generate-options': [issueId: number]
  'create-candidate': [issueId: number]
  'ignore-issue': [issueId: number]
  'apply-candidate': [revisionId: number]
  'reject-candidate': [revisionId: number]
}>()

// Active tab in the drawer
const activeTab = ref<'timeline' | 'issues' | 'candidate'>('timeline')

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    direction="rtl"
    size="420px"
    :with-header="true"
    title="版本与修订"
    data-testid="studio-version-inspector"
    @update:model-value="emit('update:modelValue', $event)"
    @close="handleClose"
  >
    <div class="studio-version-inspector">
      <!-- Tab navigation -->
      <div class="studio-version-inspector__tabs">
        <button
          class="studio-version-inspector__tab"
          :class="{ 'is-active': activeTab === 'timeline' }"
          data-testid="inspector-tab-timeline"
          @click="activeTab = 'timeline'"
        >
          版本时间线
        </button>
        <button
          class="studio-version-inspector__tab"
          :class="{ 'is-active': activeTab === 'issues' }"
          data-testid="inspector-tab-issues"
          @click="activeTab = 'issues'"
        >
          审查问题
        </button>
        <button
          v-if="candidate"
          class="studio-version-inspector__tab"
          :class="{ 'is-active': activeTab === 'candidate' }"
          data-testid="inspector-tab-candidate"
          @click="activeTab = 'candidate'"
        >
          候选修订
        </button>
      </div>

      <!-- Timeline tab -->
      <div v-if="activeTab === 'timeline'" class="studio-version-inspector__panel">
        <DraftVersionTimeline
          :versions="versions"
          :current-version="currentVersion"
          @create-version="emit('create-version', $event)"
          @restore="emit('restore', $event)"
          @select-version="emit('select-version', $event)"
        >
          <template #internal-revisions>
            <RevisionHistoryPanel :revisions="revisions" />
          </template>
        </DraftVersionTimeline>
      </div>

      <!-- Issues tab -->
      <div v-if="activeTab === 'issues'" class="studio-version-inspector__panel">
        <ReviewIssuePanel
          :issues="issues"
          :selected-issue-id="selectedIssueId"
          @generate-options="emit('generate-options', $event)"
          @create-candidate="emit('create-candidate', $event)"
          @ignore="emit('ignore-issue', $event)"
        />
      </div>

      <!-- Candidate tab -->
      <div v-if="activeTab === 'candidate' && candidate" class="studio-version-inspector__panel">
        <RevisionCandidatePanel
          :candidate="candidate"
          @apply="emit('apply-candidate', $event)"
          @reject="emit('reject-candidate', $event)"
        />
      </div>
    </div>
  </el-drawer>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio-version-inspector {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid $color-border;
    flex-shrink: 0;
  }

  &__tab {
    padding: $spacing-sm $spacing-md;
    font-size: $font-size-sm;
    color: $color-text-secondary;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: color $transition-fast, border-color $transition-fast;

    &:hover {
      color: $color-text;
    }

    &.is-active {
      color: $color-primary-dark;
      border-bottom-color: $color-primary;
    }
  }

  &__panel {
    flex: 1;
    overflow-y: auto;
    padding: $spacing-md;
  }
}
</style>
