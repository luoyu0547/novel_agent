<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'
</script>
<template>
  <div class="app-layout">
    <AppHeader />
    <div class="app-layout__body">
      <AppSidebar />
      <main class="app-layout__content"><router-view /></main>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-layout { min-height: 100vh; display: flex; flex-direction: column;
  &__body { display: flex; flex: 1; }
  &__content { flex: 1; padding: $spacing-lg; overflow-y: auto; background: $color-bg; } }
</style>
