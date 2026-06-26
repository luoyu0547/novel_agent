<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
<template>
  <el-menu
    :default-active="route.path"
    router
    class="app-sidebar"
  >
    <el-menu-item index="/novels">
      <span>我的小说</span>
    </el-menu-item>
  </el-menu>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-sidebar {
  border-right: none;
  --el-menu-bg-color: $color-bg-card;
  --el-menu-text-color: $color-text-secondary;
  --el-menu-active-color: $color-primary-dark;
  --el-menu-hover-bg-color: $color-bg-secondary;
  --el-menu-item-height: 44px;
}
</style>
