<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/common/AppButton.vue'
const router = useRouter()
const auth = useAuthStore()
function handleLogout() { auth.logout(); router.push('/login') }
</script>
<template>
  <header class="app-header">
    <div class="app-header__left"><span class="app-header__logo">Novel Agent</span></div>
    <div class="app-header__right">
      <span v-if="auth.userInfo" class="app-header__user">{{ auth.userInfo.username }}</span>
      <AppButton variant="ghost" size="sm" @click="handleLogout">退出登录</AppButton>
    </div>
  </header>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-header { display: flex; align-items: center; justify-content: space-between; height: 56px; padding: 0 $spacing-lg; background: $color-bg-card; border-bottom: 1px solid $color-border;
  &__logo { font-family: $font-family; font-size: $font-size-lg; font-weight: 700; color: $color-primary-dark; }
  &__right { display: flex; align-items: center; gap: $spacing-md; }
  &__user { font-size: $font-size-sm; color: $color-text-secondary; } }
</style>
