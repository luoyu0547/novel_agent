<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{ novelId: number }>()
const route = useRoute()
const router = useRouter()

const tabs = computed(() => [
  { label: '章节', path: `/novels/${props.novelId}` },
  { label: '角色', path: `/novels/${props.novelId}/characters` },
  { label: '设定', path: `/novels/${props.novelId}/settings` },
])
</script>

<template>
  <el-tabs :model-value="route.path" @tab-change="(p: string) => router.push(p)" class="workspace-tabs">
    <el-tab-pane v-for="tab in tabs" :key="tab.path" :label="tab.label" :name="tab.path" />
  </el-tabs>
</template>

<style scoped lang="scss">
.workspace-tabs { margin-bottom: 16px; }
</style>
