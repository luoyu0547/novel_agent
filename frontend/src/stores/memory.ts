import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as memoryApi from '@/api/memory'
import type { CharacterCreate, CharacterProfile, CharacterUpdate, WorldSetting, WorldSettingCreate, WorldSettingUpdate } from '@/types'

export const useMemoryStore = defineStore('memory', () => {
  const characters = ref<CharacterProfile[]>([])
  const worldSettings = ref<WorldSetting[]>([])

  async function loadCharacters(novelId: number) { characters.value = await memoryApi.listCharacters(novelId) }
  async function createCharacter(novelId: number, data: CharacterCreate) { const item = await memoryApi.createCharacter(novelId, data); characters.value.unshift(item) }
  async function updateCharacter(novelId: number, characterId: number, data: CharacterUpdate) { const item = await memoryApi.updateCharacter(novelId, characterId, data); characters.value = characters.value.map((c) => c.id === characterId ? item : c) }
  async function deleteCharacter(novelId: number, characterId: number) { await memoryApi.deleteCharacter(novelId, characterId); characters.value = characters.value.filter((c) => c.id !== characterId) }

  async function loadWorldSettings(novelId: number) { worldSettings.value = await memoryApi.listWorldSettings(novelId) }
  async function createWorldSetting(novelId: number, data: WorldSettingCreate) { const item = await memoryApi.createWorldSetting(novelId, data); worldSettings.value.unshift(item) }
  async function updateWorldSetting(novelId: number, settingId: number, data: WorldSettingUpdate) { const item = await memoryApi.updateWorldSetting(novelId, settingId, data); worldSettings.value = worldSettings.value.map((s) => s.id === settingId ? item : s) }
  async function deleteWorldSetting(novelId: number, settingId: number) { await memoryApi.deleteWorldSetting(novelId, settingId); worldSettings.value = worldSettings.value.filter((s) => s.id !== settingId) }

  return { characters, worldSettings, loadCharacters, createCharacter, updateCharacter, deleteCharacter, loadWorldSettings, createWorldSetting, updateWorldSetting, deleteWorldSetting }
})
