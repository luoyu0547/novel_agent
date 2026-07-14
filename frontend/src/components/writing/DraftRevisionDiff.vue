<script setup lang="ts">
import { computed } from 'vue'
import type { DraftRevision, RevisionPatch } from '@/types/revision'

const props = defineProps<{
  revision: DraftRevision
  selected: boolean
}>()

const emit = defineEmits<{
  apply: [revisionId: number]
}>()

const patches = computed<RevisionPatch[]>(() => props.revision.patches_json ?? [])

const diff = computed(() => props.revision.diff_json as {
  unchanged?: string[]
  deleted?: string[]
  added?: string[]
})

const hasPatches = computed(() => patches.value.length > 0)
</script>

<template>
  <div class="draft-revision-diff" :class="{ 'draft-revision-diff--selected': selected }">
    <div class="draft-revision-diff__header">
      <span>修订 #{{ revision.id }}</span>
      <el-tag size="small">{{ revision.status }}</el-tag>
    </div>

    <div class="draft-revision-diff__reason">
      <p>{{ revision.reason }}</p>
    </div>

    <!-- Render exact patches with surrounding context when available -->
    <div v-if="hasPatches" class="draft-revision-diff__patches">
      <div
        v-for="(patch, idx) in patches"
        :key="'p-' + idx"
        class="draft-revision-diff__patch"
      >
        <p class="draft-revision-diff__patch-reason">{{ patch.reason }}</p>
        <div class="draft-revision-diff__patch-diff">
          <div class="draft-revision-diff__patch-old">
            <span class="draft-revision-diff__patch-label">删除：</span>
            <span class="draft-revision-diff__patch-text draft-revision-diff__patch-text--deleted">{{ patch.original_text }}</span>
          </div>
          <div class="draft-revision-diff__patch-new">
            <span class="draft-revision-diff__patch-label">添加：</span>
            <span class="draft-revision-diff__patch-text draft-revision-diff__patch-text--added">{{ patch.replacement_text }}</span>
          </div>
        </div>
        <p class="draft-revision-diff__patch-location">位置：{{ patch.start_offset }}-{{ patch.end_offset }}</p>
      </div>
    </div>

    <!-- Fallback to diff_json format for backward compat -->
    <div v-else class="draft-revision-diff__content">
      <div v-if="diff.unchanged?.length" class="draft-revision-diff__unchanged">
        <p v-for="(seg, idx) in diff.unchanged" :key="'u-' + idx" class="unchanged">{{ seg }}</p>
      </div>
      <div v-if="diff.deleted?.length" class="draft-revision-diff__deleted">
        <p v-for="(seg, idx) in diff.deleted" :key="'d-' + idx" class="deleted">{{ seg }}</p>
      </div>
      <div v-if="diff.added?.length" class="draft-revision-diff__added">
        <p v-for="(seg, idx) in diff.added" :key="'a-' + idx" class="added">{{ seg }}</p>
      </div>
    </div>

    <div class="draft-revision-diff__actions">
      <el-button
        size="small"
        type="primary"
        :disabled="!selected"
        @click="emit('apply', revision.id)"
      >
        应用
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.draft-revision-diff--selected {
  border-color: #409eff;
  background: #f0f7ff;
}

.draft-revision-diff__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.draft-revision-diff__reason {
  margin-bottom: 8px;
}

.draft-revision-diff__patch {
  padding: 8px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 8px;
}

.draft-revision-diff__patch-reason {
  font-size: 12px;
  color: #909399;
  margin: 0 0 4px;
}

.draft-revision-diff__patch-diff {
  margin: 4px 0;
}

.draft-revision-diff__patch-old,
.draft-revision-diff__patch-new {
  font-size: 13px;
  margin: 2px 0;
}

.draft-revision-diff__patch-label {
  font-weight: 500;
  color: #606266;
}

.draft-revision-diff__patch-text {
  font-family: monospace;
  font-size: 12px;
}

.draft-revision-diff__patch-text--deleted {
  color: #f56c6c;
  text-decoration: line-through;
}

.draft-revision-diff__patch-text--added {
  color: #67c23a;
}

.draft-revision-diff__patch-location {
  font-size: 11px;
  color: #c0c4cc;
  margin: 4px 0 0;
}

.draft-revision-diff__content {
  margin-bottom: 8px;
}

.unchanged {
  color: #606266;
  font-size: 13px;
  margin: 2px 0;
}

.deleted {
  color: #f56c6c;
  text-decoration: line-through;
  font-size: 13px;
  margin: 2px 0;
}

.added {
  color: #67c23a;
  font-size: 13px;
  margin: 2px 0;
}

.draft-revision-diff__actions {
  display: flex;
  gap: 8px;
}
</style>
