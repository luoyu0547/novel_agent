import client from './client'
import type { CharacterCreate, CharacterProfile, CharacterUpdate, WorldSetting, WorldSettingCreate, WorldSettingUpdate } from '@/types'

export function listCharacters(novelId: number): Promise<CharacterProfile[]> { return client.get(`/novels/${novelId}/characters`) }
export function createCharacter(novelId: number, data: CharacterCreate): Promise<CharacterProfile> { return client.post(`/novels/${novelId}/characters`, data) }
export function getCharacter(novelId: number, characterId: number): Promise<CharacterProfile> { return client.get(`/novels/${novelId}/characters/${characterId}`) }
export function updateCharacter(novelId: number, characterId: number, data: CharacterUpdate): Promise<CharacterProfile> { return client.put(`/novels/${novelId}/characters/${characterId}`, data) }
export function deleteCharacter(novelId: number, characterId: number): Promise<void> { return client.delete(`/novels/${novelId}/characters/${characterId}`) }

export function listWorldSettings(novelId: number): Promise<WorldSetting[]> { return client.get(`/novels/${novelId}/settings`) }
export function createWorldSetting(novelId: number, data: WorldSettingCreate): Promise<WorldSetting> { return client.post(`/novels/${novelId}/settings`, data) }
export function getWorldSetting(novelId: number, settingId: number): Promise<WorldSetting> { return client.get(`/novels/${novelId}/settings/${settingId}`) }
export function updateWorldSetting(novelId: number, settingId: number, data: WorldSettingUpdate): Promise<WorldSetting> { return client.put(`/novels/${novelId}/settings/${settingId}`, data) }
export function deleteWorldSetting(novelId: number, settingId: number): Promise<void> { return client.delete(`/novels/${novelId}/settings/${settingId}`) }
