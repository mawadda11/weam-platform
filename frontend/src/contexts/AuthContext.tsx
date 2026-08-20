import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { apiClient, tokenStorage } from '../api/client'
import type { AuthResponse, User, UserRole } from '../types'

interface RegisterInput {
  email: string
  full_name: string
  password: string
  role: UserRole
  provider_specialty?: string
}

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (input: RegisterInput) => Promise<User>
  loginWithGoogleCredential: (credential: string, role?: UserRole, specialty?: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem('weam_user')
    try {
      return raw ? (JSON.parse(raw) as User) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(tokenStorage.hasAccessToken())

  useEffect(() => {
    if (!tokenStorage.hasAccessToken()) {
      setLoading(false)
      return
    }

    apiClient
      .get<User>('/auth/me')
      .then((response) => {
        setUser(response.data)
        localStorage.setItem('weam_user', JSON.stringify(response.data))
      })
      .catch(() => {
        tokenStorage.clear()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const applyAuth = (auth: AuthResponse) => {
    tokenStorage.set(auth)
    setUser(auth.user)
    return auth.user
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async login(email, password) {
        const response = await apiClient.post<AuthResponse>('/auth/login', { email, password })
        return applyAuth(response.data)
      },
      async register(input) {
        const response = await apiClient.post<AuthResponse>('/auth/register', input)
        return applyAuth(response.data)
      },
      async loginWithGoogleCredential(credential, role, specialty) {
        const response = await apiClient.post<AuthResponse>('/auth/google', {
          credential,
          role,
          provider_specialty: specialty || undefined,
        })
        return applyAuth(response.data)
      },
      logout() {
        tokenStorage.clear()
        setUser(null)
      },
    }),
    [user, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
