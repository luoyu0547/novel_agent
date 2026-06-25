<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
const route = useRoute(); const router = useRouter()
interface NavItem { label: string; path: string; icon: string }
const navItems: NavItem[] = [{ label: '我的小说', path: '/novels', icon: '' }]
</script>
<template>
  <aside class="app-sidebar">
    <nav class="app-sidebar__nav">
      <button v-for="item in navItems" :key="item.path" class="app-sidebar__item" :class="{ 'app-sidebar__item--active': route.path.startsWith('/novels') }" @click="router.push(item.path)">
        <span class="app-sidebar__label">{{ item.label }}</span>
      </button>
    </nav>
  </aside>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-sidebar { width: 200px; background: $color-bg-card; border-right: 1px solid $color-border; padding: $spacing-md 0;
  &__nav { display: flex; flex-direction: column; gap: 2px; }
  &__item { display: flex; align-items: center; gap: $spacing-sm; padding: $spacing-sm $spacing-lg; font-size: $font-size-sm; color: $color-text-secondary; transition: all $transition-fast; text-align: left; width: 100%;
    &:hover { background: $color-bg-secondary; color: $color-text; }
    &--active { background: $color-bg-secondary; color: $color-primary-dark; font-weight: 600; border-right: 3px solid $color-primary; } } }
</style>
