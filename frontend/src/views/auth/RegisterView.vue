<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'

const router = useRouter()
const auth = useAuthStore()
const username = ref(''); const password = ref(''); const confirmPassword = ref(''); const error = ref(''); const loading = ref(false)

async function handleRegister() {
  if (!username.value || !password.value) { error.value = '请填写用户名和密码'; return }
  if (username.value.length < 2 || username.value.length > 50) { error.value = '用户名长度需在 2-50 字符之间'; return }
  if (password.value.length < 6) { error.value = '密码长度不能少于 6 位'; return }
  if (password.value !== confirmPassword.value) { error.value = '两次密码输入不一致'; return }
  error.value = ''; loading.value = true
  try { await auth.register({ username: username.value, password: password.value }); router.push('/novels') }
  catch (e: unknown) { error.value = (e as Error).message || '注册失败' }
  finally { loading.value = false }
}
</script>
<template>
  <div class="auth-view">
    <div class="auth-card">
      <h1 class="auth-card__title">Novel Agent</h1>
      <p class="auth-card__subtitle">创建新账号</p>
      <form class="auth-card__form" @submit.prevent="handleRegister">
        <AppInput v-model="username" placeholder="用户名" />
        <AppInput v-model="password" type="password" placeholder="密码" />
        <AppInput v-model="confirmPassword" type="password" placeholder="确认密码" />
        <p v-if="error" class="auth-card__error">{{ error }}</p>
        <AppButton type="submit" :loading="loading" class="auth-card__submit">注册</AppButton>
      </form>
      <p class="auth-card__switch">已有账号？<router-link to="/login">登录</router-link></p>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.auth-view { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: $color-bg; }
.auth-card { width: 100%; max-width: 400px; padding: $spacing-2xl; background: $color-bg-card; border-radius: $radius-xl; box-shadow: $shadow-md; border: 1px solid $color-border; }
.auth-card__title { font-family: $font-family; font-size: $font-size-2xl; text-align: center; color: $color-primary-dark; margin-bottom: $spacing-xs; }
.auth-card__subtitle { text-align: center; color: $color-text-secondary; margin-bottom: $spacing-xl; font-size: $font-size-sm; }
.auth-card__form { display: flex; flex-direction: column; gap: $spacing-md; }
.auth-card__error { font-size: $font-size-sm; color: $color-error; }
.auth-card__submit { width: 100%; margin-top: $spacing-sm; }
.auth-card__switch { margin-top: $spacing-lg; text-align: center; font-size: $font-size-sm; color: $color-text-secondary; }
</style>
