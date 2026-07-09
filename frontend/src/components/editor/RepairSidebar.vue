<script setup lang="ts">
import type { RepairLog, PendingRepair } from '@/types/writing'

defineProps<{
  repairLogs: RepairLog[]
  pendingRepairs: PendingRepair[]
}>()
</script>

<template>
  <aside class="repair-sidebar">
    <div v-for="repair in pendingRepairs" :key="repair.id">
      {{ repair.description }}
    </div>
    <div v-for="log in repairLogs" :key="log.id">
      {{ log.description }}
    </div>
  </aside>
</template>

<style scoped lang="scss">
.repair-sidebar {
  width: 320px;
  border-left: 1px solid var(--color-border, #e4e7ed);
  overflow-y: auto;
  padding: 16px;
}
</style>
