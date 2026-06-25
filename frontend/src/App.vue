<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
onMounted(() => { auth.restoreSession() })
</script>

<template>
  <router-view />
</template>

<style lang="scss">
@use '@/styles/reset';
@use '@/styles/global';
</style>
