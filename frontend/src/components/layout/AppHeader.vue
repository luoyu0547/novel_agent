<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
const router = useRouter()
const auth = useAuthStore()
function handleLogout() { auth.logout(); router.push('/login') }
</script>
<template>
  <div class="app-header">
    <div class="app-header__left">
      <span class="app-header__logo">Novel Agent</span>
    </div>
    <div class="app-header__right">
      <span v-if="auth.userInfo" class="app-header__user">{{ auth.userInfo.username }}</span>
      <el-button text size="small" @click="handleLogout">退出登录</el-button>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  height: 56px; padding: 0 $spacing-lg;
  &__logo { font-size: $font-size-lg; font-weight: 700; color: $color-primary-dark; }
  &__right { display: flex; align-items: center; gap: $spacing-md; }
  &__user { font-size: $font-size-sm; color: $color-text-secondary; } }
</style>
