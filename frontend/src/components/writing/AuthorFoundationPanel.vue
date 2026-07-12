<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AuthorFoundation, AuthorFoundationUpdate } from '@/types/plotPlanning'

const props = defineProps<{
  foundation: AuthorFoundation | null
  loading: boolean
}>()

const emit = defineEmits<{
  save: [data: AuthorFoundationUpdate]
}>()

const outline = ref('')
const currentIntent = ref('')
const stageGoal = ref('')

watch(() => props.foundation, (f) => {
  if (f) {
    outline.value = f.outline
    currentIntent.value = f.current_intent
    stageGoal.value = f.stage_goal
  }
}, { immediate: true })

function handleSave() {
  emit('save', {
    outline: outline.value,
    current_intent: currentIntent.value,
    stage_goal: stageGoal.value,
  })
}
</script>

<template>
  <div class="author-foundation-panel">
    <h3>作者资料</h3>
    <el-input v-model="outline" placeholder="大纲" type="textarea" :rows="3" size="small" />
    <el-input v-model="currentIntent" placeholder="当前意图" type="textarea" :rows="2" size="small" />
    <el-input v-model="stageGoal" placeholder="阶段目标" type="textarea" :rows="2" size="small" />
    <el-button
      data-testid="save-foundation"
      size="small"
      type="primary"
      :loading="loading"
      @click="handleSave"
    >
      保存作者资料
    </el-button>
  </div>
</template>

<style lang="scss" scoped>
.author-foundation-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
