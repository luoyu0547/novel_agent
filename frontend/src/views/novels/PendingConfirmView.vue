<script setup lang="ts">
import { usePendingMemoryStore } from '@/stores/pendingMemory'
import type { PendingMemory } from '@/types'

const route = useRoute()
const store = usePendingMemoryStore()
const novelId = Number(route.params.id)

const memoryLabels: Record<string, string> = {
  character_change: '角色变化',
  plot_fact: '剧情事实',
  world_setting: '世界观设定',
  foreshadowing: '伏笔候选',
}

const statusLabels: Record<string, string> = {
  pending: '待确认',
  confirmed: '已确认',
  rejected: '已拒绝',
}

const statusTypes: Record<string, string> = {
  pending: 'warning',
  confirmed: 'success',
  rejected: 'info',
}

const grouped = computed(() => {
  const groups: Record<string, PendingMemory[]> = {}
  for (const m of store.memories) {
    const key = memoryLabels[m.memory_type] || m.memory_type
    if (!groups[key]) groups[key] = []
    groups[key].push(m)
  }
  return groups
})

const pendingIds = computed(() =>
  store.memories.filter(m => m.status === 'pending').map(m => m.id),
)

async function handleConfirm(id: number) {
  await store.confirm(id)
  ElMessage.success('已确认')
}

async function handleReject(id: number) {
  await store.reject(id)
  ElMessage.success('已拒绝')
}

async function handleBatch(action: 'confirm' | 'reject') {
  if (!pendingIds.value.length) {
    ElMessage.info('没有待确认的条目')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定${action === 'confirm' ? '确认' : '拒绝'}全部 ${pendingIds.value.length} 条待确认条目？`,
      '提示',
    )
    await store.batchAction(pendingIds.value, action)
    ElMessage.success('操作完成')
  } catch { /* cancelled */ }
}

onMounted(() => store.fetchMemories(novelId))
</script>

<template>
  <div class="pending-confirm">
    <div class="page-header">
      <h2>待确认记忆</h2>
      <div v-if="pendingIds.length" class="batch-actions">
        <el-button type="primary" @click="handleBatch('confirm')">
          确认全部 ({{ pendingIds.length }})
        </el-button>
        <el-button @click="handleBatch('reject')">
          拒绝全部 ({{ pendingIds.length }})
        </el-button>
      </div>
    </div>

    <div v-if="store.loading" v-loading="store.loading" class="loading-wrap" />

    <div v-else-if="!store.memories.length" class="empty">
      <el-empty description="暂无待确认记忆" />
    </div>

    <div v-else v-for="(items, type) in grouped" :key="type" class="memory-group">
      <h3 class="group-title">{{ type }} ({{ items.length }})</h3>
      <el-card v-for="item in items" :key="item.id" class="memory-card" :class="item.status">
        <div class="card-header">
          <el-tag :type="statusTypes[item.status] as any" size="small">
            {{ statusLabels[item.status] }}
          </el-tag>
          <span class="card-time">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
        </div>
        <pre class="card-content">{{ JSON.stringify(item.content, null, 2) }}</pre>
        <div v-if="item.status === 'pending'" class="card-actions">
          <el-button type="primary" size="small" @click="handleConfirm(item.id)">确认</el-button>
          <el-button size="small" @click="handleReject(item.id)">拒绝</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped lang="scss">
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.memory-group {
  margin-bottom: 24px;
}
.group-title {
  margin-bottom: 12px;
  font-size: 16px;
  color: var(--el-text-color-primary);
}
.memory-card {
  margin-bottom: 12px;
  &.confirmed { opacity: 0.7; }
  &.rejected { opacity: 0.5; }
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.card-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.card-content {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
}
.card-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.loading-wrap {
  min-height: 200px;
}
.empty {
  padding: 60px 0;
}
</style>
