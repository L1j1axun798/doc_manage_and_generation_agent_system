import { defineStore } from 'pinia'

import { isNormalizedApiError } from '@/core/http/error-normalizer'
import {
  changePassword,
  fetchCsrfToken,
  fetchCurrentUser,
  login,
  logout,
  verifyWebAuthnLogin,
} from '../api/auth.api'
import { authenticateWithWebAuthn } from '../services/webauthn'
import type { AuthUser, ChangePasswordPayload, LoginPayload } from '../auth.types'

type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'anonymous'

interface AuthState {
  user: AuthUser | null
  status: AuthStatus
  initialized: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    status: 'idle',
    initialized: false,
  }),

  getters: {
    isAuthenticated: (state) => state.status === 'authenticated' && state.user !== null,
    isSystemAdmin: (state) => state.user?.role === 'system_admin',
  },

  actions: {
    async initializeSession(): Promise<AuthUser | null> {
      if (this.initialized) {
        return this.user
      }

      this.status = 'loading'

      try {
        await fetchCsrfToken()
        this.user = await fetchCurrentUser()
        this.status = 'authenticated'
      } catch (error) {
        this.user = null
        this.status = 'anonymous'

        if (isNormalizedApiError(error) && error.status && ![401, 403].includes(error.status)) {
          throw error
        }
      } finally {
        this.initialized = true
      }

      return this.user
    },

    async login(payload: LoginPayload): Promise<AuthUser> {
      this.status = 'loading'
      await fetchCsrfToken()
      const loginResponse = await login(payload)
      const user = loginResponse.status === 'authenticated'
        ? loginResponse.user
        : await verifyWebAuthnLogin({
            pending_token: loginResponse.pending_token,
            credential: await authenticateWithWebAuthn(loginResponse.options),
          })
      this.user = user
      this.status = 'authenticated'
      this.initialized = true
      return user
    },

    async logout(): Promise<void> {
      try {
        await logout()
      } finally {
        this.user = null
        this.status = 'anonymous'
        this.initialized = true
      }
    },

    async changePassword(payload: ChangePasswordPayload): Promise<void> {
      await changePassword(payload)
      if (this.user) {
        this.user = {
          ...this.user,
          must_change_password: false,
        }
      }
    },
  },
})
