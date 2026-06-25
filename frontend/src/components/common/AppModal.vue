<script setup lang="ts">
import AppButton from './AppButton.vue'
withDefaults(defineProps<{ visible: boolean; title?: string; width?: string; confirmText?: string; cancelText?: string }>(), { width: '480px' })
const emit = defineEmits<{ 'update:visible': [value: boolean]; confirm: []; cancel: [] }>()
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click.self="emit('update:visible', false)">
        <div class="modal-content" :style="{ maxWidth: width }">
          <div class="modal-header">
            <h3 class="modal-title">{{ title }}</h3>
            <button class="modal-close" @click="emit('update:visible', false)">✕</button>
          </div>
          <div class="modal-body"><slot /></div>
          <div v-if="confirmText || cancelText" class="modal-footer">
            <AppButton v-if="cancelText" variant="secondary" @click="emit('cancel')">{{ cancelText }}</AppButton>
            <AppButton v-if="confirmText" @click="emit('confirm')">{{ confirmText }}</AppButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { width: 90%; background: $color-bg-card; border-radius: $radius-xl; box-shadow: $shadow-lg; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: $spacing-lg; border-bottom: 1px solid $color-border; }
.modal-title { font-size: $font-size-lg; font-weight: 600; }
.modal-close { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: $radius-sm; color: $color-text-secondary; transition: all $transition-fast; &:hover { background: $color-bg-secondary; color: $color-text; } }
.modal-body { padding: $spacing-lg; }
.modal-footer { display: flex; justify-content: flex-end; gap: $spacing-sm; padding: $spacing-lg; border-top: 1px solid $color-border; }
.modal-enter-active, .modal-leave-active { transition: opacity $transition-normal; .modal-content { transition: transform $transition-normal; } }
.modal-enter-from, .modal-leave-to { opacity: 0; .modal-content { transform: scale(0.95); } }
</style>
