<script setup lang="ts">
defineProps<{ modelValue: string; rows?: number; placeholder?: string; maxLength?: number; error?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="app-textarea" :class="{ 'app-textarea--error': error }">
    <textarea
      :value="modelValue" :rows="rows || 6" :placeholder="placeholder" :maxlength="maxLength"
      class="app-textarea__field"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
    <p v-if="error" class="app-textarea__error">{{ error }}</p>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-textarea { width: 100%;
  &__field { width: 100%; padding: 8px 16px; border: 1px solid $color-border; border-radius: $radius-md; background: $color-bg-card; color: $color-text; font-size: $font-size-md; line-height: 1.8; resize: vertical; transition: all $transition-fast;
    &::placeholder { color: $color-text-placeholder; }
    &:focus { border-color: $color-primary; box-shadow: 0 0 0 3px rgba($color-primary, 0.15); outline: none; } }
  &--error &__field { border-color: $color-error; }
  &__error { margin-top: 4px; font-size: $font-size-sm; color: $color-error; } }
</style>
