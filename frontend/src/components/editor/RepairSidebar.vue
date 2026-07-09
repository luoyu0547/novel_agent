<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RepairLog, PendingRepair } from '@/types/writing'
import { ArrowRight } from '@element-plus/icons-vue'
import RepairItem from './RepairItem.vue'

const props = defineProps<{
  repairLogs: RepairLog[]
  pendingRepairs: PendingRepair[]
}>()

const emit = defineEmits<{
  (e: 'resolve', repairId: number, payload: { action: 'apply' | 'dismiss'; choice_index?: number; intent_text?: string }): void
}>()

const logsExpanded = ref(false)

function handleResolve(repairId: number, payload: { action: 'apply' | 'dismiss'; choice_index?: number; intent_text?: string }) {
  emit('resolve', repairId, payload)
}

const unresolvedCount = computed(() =>
  props.pendingRepairs.filter(r => r.status === 'pending').length,
)
</script>

<template>
  <aside class="repair-sidebar">
    <div class="repair-sidebar__header">
      <h3 class="repair-sidebar__title">修复</h3>
      <el-tag v-if="unresolvedCount > 0" size="small" type="warning">
        {{ unresolvedCount }} 项待处理
      </el-tag>
    </div>

    <!-- Auto Repair Logs -->
    <div v-if="repairLogs.length > 0" class="repair-sidebar__section">
      <div class="repair-sidebar__section-header" @click="logsExpanded = !logsExpanded">
        <el-text size="small" type="info">
          自动修复 ({{ repairLogs.length }})
        </el-text>
        <el-icon :class="{ expanded: logsExpanded }">
          <ArrowRight />
        </el-icon>
      </div>
      <Transition name="collapse">
        <div v-show="logsExpanded" class="repair-sidebar__logs">
          <RepairItem
            v-for="log in repairLogs"
            :key="log.id"
            :repair="log"
            type="log"
          />
        </div>
      </Transition>
    </div>

    <!-- Pending Repairs -->
    <div class="repair-sidebar__section">
      <div class="repair-sidebar__section-header">
        <el-text size="small" type="info">待处理修复</el-text>
      </div>
      <div v-if="pendingRepairs.length === 0" class="repair-sidebar__empty">
        <el-text size="small" type="info">暂无待处理项</el-text>
      </div>
      <div v-else class="repair-sidebar__items">
        <RepairItem
          v-for="repair in pendingRepairs"
          :key="repair.id"
          :repair="repair"
          type="pending"
          @resolve="handleResolve"
        />
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.repair-sidebar {
  width: 320px;
  min-width: 320px;
  border-left: 1px solid $color-border;
  background: $color-bg-card;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.repair-sidebar__header {
  padding: $spacing-md;
  border-bottom: 1px solid $color-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.repair-sidebar__title {
  margin: 0;
  font-size: $font-size-md;
  font-weight: 600;
  color: $color-text;
}

.repair-sidebar__section {
  padding: $spacing-sm $spacing-md;
  border-bottom: 1px solid $color-border;

  &:last-child {
    border-bottom: none;
  }
}

.repair-sidebar__section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
  margin-bottom: $spacing-sm;

  .el-icon {
    transition: transform 0.2s;
    font-size: 14px;

    &.expanded {
      transform: rotate(90deg);
    }
  }
}

.repair-sidebar__logs {
  display: flex;
  flex-direction: column;
  gap: $spacing-xs;
}

.repair-sidebar__items {
  display: flex;
  flex-direction: column;
  gap: $spacing-sm;
}

.repair-sidebar__empty {
  text-align: center;
  padding: $spacing-lg 0;
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.2s ease;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
