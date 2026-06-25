<script setup lang="ts">
withDefaults(defineProps<{ padding?: string }>(), { padding: '24px' })
</script>

<template>
  <div class="app-card" :style="{ padding }"><slot /></div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-card { background: $color-bg-card; border-radius: $radius-lg; box-shadow: $shadow-sm; border: 1px solid $color-border; }
</style>
