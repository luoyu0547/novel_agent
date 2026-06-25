import client from './client'
import type { LoginRequest, RegisterRequest, AuthResponse } from '@/types'

export function login(data: LoginRequest): Promise<AuthResponse> {
  return client.post('/auth/login', data)
}
export function register(data: RegisterRequest): Promise<AuthResponse> {
  return client.post('/auth/register', data)
}
