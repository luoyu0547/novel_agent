<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{ novelId: number }>()
const route = useRoute()
const router = useRouter()

const tabs = computed(() => [
  { label: '章节', path: `/novels/${props.novelId}` },
  { label: '角色', path: `/novels/${props.novelId}/characters` },
  { label: '设定', path: `/novels/${props.novelId}/settings` },
])
</script>

<template>
  <nav class="workspace-tabs">
    <button v-for="tab in tabs" :key="tab.path" class="workspace-tabs__item" :class="{ 'workspace-tabs__item--active': route.path === tab.path }" @click="router.push(tab.path)">
      {{ tab.label }}
    </button>
  </nav>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.workspace-tabs { display: flex; gap: $spacing-sm; margin-bottom: $spacing-lg; border-bottom: 1px solid $color-border; }
.workspace-tabs__item { padding: $spacing-sm $spacing-md; color: $color-text-secondary; border-bottom: 2px solid transparent; font-size: $font-size-sm; }
.workspace-tabs__item:hover { color: $color-text; }
.workspace-tabs__item--active { color: $color-primary-dark; border-bottom-color: $color-primary; font-weight: 600; }
</style>
