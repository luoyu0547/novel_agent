<script setup lang="ts">
import AppModal from './AppModal.vue'
withDefaults(defineProps<{ visible: boolean; title?: string; content?: string; confirmText?: string; cancelText?: string; confirmVariant?: 'primary' | 'danger' }>(), { title: '确认操作', content: '确定要执行此操作吗？', confirmText: '确认', cancelText: '取消', confirmVariant: 'primary' })
const emit = defineEmits<{ 'update:visible': [value: boolean]; confirm: []; cancel: [] }>()
</script>

<template>
  <AppModal :visible="visible" :title="title" :confirm-text="confirmText" :cancel-text="cancelText"
    @update:visible="emit('update:visible', $event)" @confirm="emit('confirm')" @cancel="emit('cancel')">
    <p>{{ content }}</p>
  </AppModal>
</template>
