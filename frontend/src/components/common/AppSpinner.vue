<script setup lang="ts">
withDefaults(defineProps<{ size?: 'sm' | 'md' | 'lg' }>(), { size: 'md' })
</script>
<template><div class="app-spinner" :class="`app-spinner--${size}`" /></template>
<style scoped lang="scss">
.app-spinner { border-radius: 50%; border: 3px solid currentColor; border-top-color: transparent; animation: spin 0.6s linear infinite; color: inherit;
  &--sm { width: 20px; height: 20px; border-width: 2px; } &--md { width: 32px; height: 32px; } &--lg { width: 48px; height: 48px; border-width: 4px; } }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
