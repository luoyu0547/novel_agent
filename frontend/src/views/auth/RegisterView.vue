<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '', confirmPassword: '' })
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度需在 2-50 字符之间', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (value !== form.password) callback(new Error('两次密码输入不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function handleRegister() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    error.value = ''; loading.value = true
    try { await auth.register({ username: form.username, password: form.password }); router.push('/novels') }
    catch (e: unknown) { error.value = (e as Error).message || '注册失败' }
    finally { loading.value = false }
  })
}
</script>
<template>
  <div class="auth-view">
    <el-card class="auth-card" shadow="never">
      <template #header>
        <h1 class="auth-card__title">Novel Agent</h1>
        <p class="auth-card__subtitle">创建新账号</p>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleRegister">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" show-password />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="auth-card__error" />
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="auth-card__submit">注册</el-button>
        </el-form-item>
      </el-form>
      <div class="auth-card__switch">已有账号？<router-link to="/login">登录</router-link></div>
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
