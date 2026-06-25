<script setup lang="ts">
withDefaults(defineProps<{ text?: string }>(), { text: '暂无数据' })
</script>
<template>
  <div class="app-empty">
    <div class="app-empty__icon">📝</div>
    <p class="app-empty__text">{{ text }}</p>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-empty { display: flex; flex-direction: column; align-items: center; padding: $spacing-2xl; color: $color-text-secondary;
  &__icon { font-size: 48px; margin-bottom: $spacing-md; opacity: 0.5; } &__text { font-size: $font-size-md; } }
</style>
