<script setup lang="ts">
import { computed } from 'vue'
import type { DraftRevision } from '@/types/plotPlanning'

const props = defineProps<{
  revision: DraftRevision
  selected: boolean
}>()

const emit = defineEmits<{
  apply: [revisionId: number]
  replace: [revisionId: number]
}>()

const diff = computed(() => props.revision.diff_json as {
  unchanged?: string[]
  deleted?: string[]
  added?: string[]
})
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

    <div class="draft-revision-diff__content">
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
      <el-button
        size="small"
        type="warning"
        :disabled="!selected"
        @click="emit('replace', revision.id)"
      >
        替换
      </el-button>
    </div>
  </div>
</template>
