import client from './client'
import type { NovelCreate, NovelUpdate, NovelListItem, NovelOut, ChapterCreate, ChapterUpdate, ChapterOut } from '@/types'

export function listNovels(): Promise<NovelListItem[]> { return client.get('/novels') }
export function createNovel(data: NovelCreate): Promise<NovelListItem> { return client.post('/novels', data) }
export function getNovel(id: number): Promise<NovelOut> { return client.get(`/novels/${id}`) }
export function updateNovel(id: number, data: NovelUpdate): Promise<NovelOut> { return client.put(`/novels/${id}`, data) }
export function deleteNovel(id: number): Promise<void> { return client.delete(`/novels/${id}`) }
export function createChapter(novelId: number, data: ChapterCreate): Promise<ChapterOut> { return client.post(`/novels/${novelId}/chapters`, data) }
export function getChapter(novelId: number, chapterId: number): Promise<ChapterOut> { return client.get(`/novels/${novelId}/chapters/${chapterId}`) }
export function updateChapter(novelId: number, chapterId: number, data: ChapterUpdate): Promise<ChapterOut> { return client.put(`/novels/${novelId}/chapters/${chapterId}`, data) }
export function deleteChapter(novelId: number, chapterId: number): Promise<void> { return client.delete(`/novels/${novelId}/chapters/${chapterId}`) }
