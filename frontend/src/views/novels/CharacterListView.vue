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
    <div class="character-list">
      <NovelWorkspaceTabs :novel-id="novelId" />
      <h2 class="character-list__title">角色管理</h2>
      <p class="character-list__placeholder">角色管理功能即将上线</p>
    </div>
  </AppLayout>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.character-list { max-width: 900px; margin: 0 auto; padding-top: $spacing-lg;
  &__title { font-size: $font-size-xl; font-weight: 700; margin-bottom: $spacing-md; }
  &__placeholder { color: $color-text-secondary; } }
</style>
