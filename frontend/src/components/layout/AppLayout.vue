<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'
</script>
<template>
  <el-container class="app-layout">
    <el-header class="app-layout__header"><AppHeader /></el-header>
    <el-container class="app-layout__body">
      <el-aside width="200px" class="app-layout__aside"><AppSidebar /></el-aside>
      <el-main class="app-layout__content"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-layout {
  min-height: 100vh;
  &__header { height: 56px; padding: 0; background: $color-bg-card; border-bottom: 1px solid $color-border; }
  &__aside { background: $color-bg-card; border-right: 1px solid $color-border; }
  &__content { background: $color-bg; padding: $spacing-lg; overflow-y: auto; } }
</style>
