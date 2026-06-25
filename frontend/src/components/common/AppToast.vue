<script setup lang="ts">
import { ref } from 'vue'
interface ToastItem { id: number; message: string; type: 'success' | 'error' | 'warning' }
const toasts = ref<ToastItem[]>([])
let nextId = 0
function add(message: string, type: ToastItem['type']) { const id = nextId++; toasts.value.push({ id, message, type }); setTimeout(() => { remove(id) }, 3000) }
function remove(id: number) { toasts.value = toasts.value.filter((t) => t.id !== id) }
function success(message: string) { add(message, 'success') }
function error(message: string) { add(message, 'error') }
function warning(message: string) { add(message, 'warning') }
defineExpose({ success, error, warning })
</script>
<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div v-for="toast in toasts" :key="toast.id" class="toast-item" :class="`toast-item--${toast.type}`">{{ toast.message }}</div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.toast-container { position: fixed; top: $spacing-lg; right: $spacing-lg; z-index: 2000; display: flex; flex-direction: column; gap: $spacing-sm; }
.toast-item { padding: $spacing-sm $spacing-lg; border-radius: $radius-md; font-size: $font-size-sm; color: #fff; box-shadow: $shadow-md; min-width: 200px;
  &--success { background: $color-success; } &--error { background: $color-error; } &--warning { background: $color-warning; color: $color-text; } }
.toast-enter-active { transition: all $transition-normal; } .toast-leave-active { transition: all $transition-fast; }
.toast-enter-from { opacity: 0; transform: translateX(100%); } .toast-leave-to { opacity: 0; transform: translateX(100%); }
</style>
