export interface RegisterRequest {
  username: string
  password: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface AuthResponse {
  token: string
  user_id: number
  username: string
}

export interface User {
  id: number
  username: string
  created_at: string
  updated_at: string
}
