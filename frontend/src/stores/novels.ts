import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as novelsApi from '@/api/novels'
import type { NovelCreate, NovelUpdate, NovelListItem, NovelOut, ChapterCreate, ChapterUpdate, ChapterOut } from '@/types'

export const useNovelStore = defineStore('novel', () => {
  const novels = ref<NovelListItem[]>([])
  const currentNovel = ref<NovelOut | null>(null)
  const currentChapter = ref<ChapterOut | null>(null)

  async function loadNovels() { novels.value = await novelsApi.listNovels() }
  async function createNovel(data: NovelCreate) { const n = await novelsApi.createNovel(data); novels.value.unshift(n) }
  async function getNovel(id: number) { currentNovel.value = await novelsApi.getNovel(id) }
  async function updateNovel(id: number, data: NovelUpdate) { await novelsApi.updateNovel(id, data); if (currentNovel.value?.id === id) currentNovel.value = await novelsApi.getNovel(id) }
  async function deleteNovel(id: number) { await novelsApi.deleteNovel(id); novels.value = novels.value.filter((n) => n.id !== id) }
  async function createChapter(novelId: number, data: ChapterCreate) { const c = await novelsApi.createChapter(novelId, data); if (currentNovel.value?.id === novelId) { currentNovel.value.chapters = currentNovel.value.chapters || []; currentNovel.value.chapters.push(c) } }
  async function loadChapter(novelId: number, chapterId: number) { currentChapter.value = await novelsApi.getChapter(novelId, chapterId) }
  async function updateChapter(novelId: number, chapterId: number, data: ChapterUpdate) { await novelsApi.updateChapter(novelId, chapterId, data); if (currentNovel.value?.id === novelId) currentNovel.value = await novelsApi.getNovel(novelId) }
  async function deleteChapter(novelId: number, chapterId: number) { await novelsApi.deleteChapter(novelId, chapterId); if (currentNovel.value?.id === novelId && currentNovel.value.chapters) currentNovel.value.chapters = currentNovel.value.chapters.filter((c) => c.id !== chapterId) }

  return { novels, currentNovel, currentChapter, loadNovels, createNovel, getNovel, updateNovel, deleteNovel, createChapter, loadChapter, updateChapter, deleteChapter }
})
