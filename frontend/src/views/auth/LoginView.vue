<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    error.value = ''; loading.value = true
    try { await auth.login(form); router.push('/novels') }
    catch (e: unknown) { error.value = (e as Error).message || '登录失败' }
    finally { loading.value = false }
  })
}
</script>
<template>
  <div class="auth-view">
    <el-card class="auth-card" shadow="never">
      <template #header>
        <h1 class="auth-card__title">Novel Agent</h1>
        <p class="auth-card__subtitle">登录你的账号</p>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="auth-card__error" />
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="auth-card__submit">登录</el-button>
        </el-form-item>
      </el-form>
      <div class="auth-card__switch">还没有账号？<router-link to="/register">注册</router-link></div>
    </el-card>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.auth-view { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: $color-bg; }
.auth-card { width: 100%; max-width: 420px;
  :deep(.el-card__header) { text-align: center; border-bottom: 1px solid $color-border; }
  &__title { font-size: $font-size-2xl; color: $color-primary-dark; margin: 0; }
  &__subtitle { color: $color-text-secondary; font-size: $font-size-sm; margin: $spacing-xs 0 0; }
  &__error { margin-bottom: $spacing-md; }
  &__submit { width: 100%; }
  &__switch { margin-top: $spacing-md; text-align: center; font-size: $font-size-sm; color: $color-text-secondary;
    a { color: $color-primary-dark; } } }
</style>
