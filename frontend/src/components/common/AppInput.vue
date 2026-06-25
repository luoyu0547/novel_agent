<script setup lang="ts">
defineProps<{ modelValue: string; type?: 'text' | 'password'; placeholder?: string; error?: string; size?: 'sm' | 'md' | 'lg'; disabled?: boolean }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="app-input" :class="{ 'app-input--error': error }">
    <input
      :type="type || 'text'" :value="modelValue" :placeholder="placeholder"
      :class="[`app-input__field`, `app-input__field--${size || 'md'}`]"
      :disabled="disabled"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="app-input__error">{{ error }}</p>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-input { width: 100%;
  &__field { width: 100%; border: 1px solid $color-border; border-radius: $radius-md; background: $color-bg-card; color: $color-text; transition: all $transition-fast;
    &::placeholder { color: $color-text-placeholder; }
    &:focus { border-color: $color-primary; box-shadow: 0 0 0 3px rgba($color-primary, 0.15); outline: none; }
    &--sm { padding: 4px 8px; font-size: $font-size-sm; }
    &--md { padding: 8px 16px; font-size: $font-size-md; }
    &--lg { padding: 16px 24px; font-size: $font-size-lg; } }
  &--error &__field { border-color: $color-error; }
  &__error { margin-top: 4px; font-size: $font-size-sm; color: $color-error; } }
</style>
