<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}>(), { variant: 'primary', size: 'md', loading: false, disabled: false })

defineEmits<{ click: [e: MouseEvent] }>()
</script>

<template>
  <button
    class="app-btn"
    :class="[`app-btn--${variant}`, `app-btn--${size}`, { 'app-btn--loading': loading }]"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="app-btn__spinner" />
    <slot />
  </button>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; border-radius: $radius-md; font-weight: 500; transition: all $transition-fast; white-space: nowrap;
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  &--sm { padding: 4px 16px; font-size: $font-size-sm; }
  &--md { padding: 8px 24px; font-size: $font-size-md; }
  &--lg { padding: 16px 32px; font-size: $font-size-lg; }
  &--primary { background: $color-primary; color: #fff; &:not(:disabled):hover { background: $color-primary-dark; } }
  &--secondary { background: $color-bg-secondary; color: $color-text; &:not(:disabled):hover { background: $color-border; } }
  &--ghost { background: transparent; color: $color-text-secondary; &:not(:disabled):hover { background: $color-bg-secondary; color: $color-text; } }
  &--danger { background: $color-error; color: #fff; &:not(:disabled):hover { background: darken($color-error, 8%); } }
  &--loading { cursor: wait; }
  &__spinner { width: 16px; height: 16px; border: 2px solid currentColor; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; }
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
