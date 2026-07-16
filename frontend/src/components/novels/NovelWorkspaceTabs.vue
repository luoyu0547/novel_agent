<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TabPaneName } from 'element-plus'
import { usePendingMemoryStore } from '@/stores/pendingMemory'

const props = defineProps<{ novelId: number }>()
const route = useRoute()
const router = useRouter()
const store = usePendingMemoryStore()

const pendingBadge = computed(() => {
  const count = store.pendingCount()
  return count > 0 ? count : undefined
})

const tabs = computed(() => [
  { label: '章节', path: `/novels/${props.novelId}` },
  { label: '角色', path: `/novels/${props.novelId}/characters` },
  { label: '设定', path: `/novels/${props.novelId}/settings` },
  { label: '待确认', path: `/novels/${props.novelId}/pending`, badge: pendingBadge.value },
  { label: '创作工坊', path: `/novels/${props.novelId}/studio` },
])

onMounted(() => { store.fetchMemories(props.novelId) })
</script>

<template>
  <el-tabs :model-value="route.path" @tab-change="(p: TabPaneName) => router.push(p as string)" class="workspace-tabs">
    <el-tab-pane v-for="tab in tabs" :key="tab.path" :label="tab.label" :name="tab.path">
      <template #label>
        <span>
          {{ tab.label }}
          <el-badge v-if="tab.badge" :value="tab.badge" :hidden="!tab.badge" />
        </span>
      </template>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped lang="scss">
.workspace-tabs { margin-bottom: 16px; }
</style>
