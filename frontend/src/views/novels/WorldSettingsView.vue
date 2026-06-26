<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import AppLayout from '@/components/layout/AppLayout.vue'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'

const route = useRoute()
const novelStore = useNovelStore()
const novelId = Number(route.params.id)

onMounted(async () => { await novelStore.getNovel(novelId) })
</script>

<template>
  <AppLayout>
    <div class="world-settings">
      <NovelWorkspaceTabs :novel-id="novelId" />
      <h2 class="world-settings__title">世界设定</h2>
      <p class="world-settings__placeholder">世界设定功能即将上线</p>
    </div>
  </AppLayout>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.world-settings { max-width: 900px; margin: 0 auto; padding-top: $spacing-lg;
  &__title { font-size: $font-size-xl; font-weight: 700; margin-bottom: $spacing-md; }
  &__placeholder { color: $color-text-secondary; } }
</style>
