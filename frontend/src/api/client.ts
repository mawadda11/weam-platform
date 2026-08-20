import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type { AuthResponse } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
const ACCESS_KEY = 'weam_access_token'
const REFRESH_KEY = 'weam_refresh_token'

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem(ACCESS_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (!refreshToken) return null

  try {
    const response = await axios.post<AuthResponse>(`${API_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    })
    localStorage.setItem(ACCESS_KEY, response.data.access_token)
    localStorage.setItem(REFRESH_KEY, response.data.refresh_token)
    return response.data.access_token
  } catch {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem('weam_user')
    return null
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    if (!original || error.response?.status !== 401 || original._retried || original.url?.includes('/auth/')) {
      return Promise.reject(error)
    }

    original._retried = true
    refreshPromise ??= refreshAccessToken().finally(() => {
      refreshPromise = null
    })
    const newToken = await refreshPromise
    if (!newToken) return Promise.reject(error)

    original.headers.Authorization = `Bearer ${newToken}`
    return apiClient(original)
  },
)

export const tokenStorage = {
  set(auth: AuthResponse) {
    localStorage.setItem(ACCESS_KEY, auth.access_token)
    localStorage.setItem(REFRESH_KEY, auth.refresh_token)
    localStorage.setItem('weam_user', JSON.stringify(auth.user))
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem('weam_user')
  },
  hasAccessToken() {
    return Boolean(localStorage.getItem(ACCESS_KEY))
  },
  getAccessToken() {
    return localStorage.getItem(ACCESS_KEY)
  },
}
