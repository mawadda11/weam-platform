export type UserRole = 'guardian' | 'care_provider' | 'center' | 'admin'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  provider_specialty?: string | null
  verification_status: 'verified' | 'unverified' | 'rejected'
  auth_provider: string
  created_at: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user: User
}

export interface ChildProfile {
  id: string
  first_name: string
  preferred_name?: string | null
  birth_date?: string | null
  gender?: string | null
  conditions: string[]
  needs: string[]
  support_requirements: string[]
  services: string[]
  summary?: string | null
  guardian_type: 'primary' | 'secondary'
  created_at: string
  updated_at: string
}

export interface ChildInput {
  first_name: string
  preferred_name?: string
  birth_date?: string
  gender?: string
  conditions: string[]
  needs: string[]
  support_requirements: string[]
  services: string[]
  summary?: string
}
