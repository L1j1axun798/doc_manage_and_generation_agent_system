import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AuthUser } from '@/modules/auth/auth.types'
import { useAuthStore } from '@/modules/auth/stores/auth.store'

const mocks = vi.hoisted(() => ({
  authenticateWithWebAuthn: vi.fn(),
  fetchCsrfToken: vi.fn(),
  login: vi.fn(),
  verifyWebAuthnLogin: vi.fn(),
}))

vi.mock('@/modules/auth/api/auth.api', () => ({
  changePassword: vi.fn(),
  fetchCsrfToken: mocks.fetchCsrfToken,
  fetchCurrentUser: vi.fn(),
  login: mocks.login,
  logout: vi.fn(),
  verifyWebAuthnLogin: mocks.verifyWebAuthnLogin,
}))

vi.mock('@/modules/auth/services/webauthn', () => ({
  authenticateWithWebAuthn: mocks.authenticateWithWebAuthn,
}))

const user: AuthUser = {
  id: 1,
  username: 'operator',
  real_name: 'Operator',
  employee_no: null,
  role: 'data_operator',
  phone: '',
  email: '',
  is_active: true,
  must_change_password: false,
  webauthn_enabled: true,
  webauthn_credentials_count: 1,
  created_at: '2026-08-07T00:00:00+08:00',
}

describe('auth store login verification modes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mocks.fetchCsrfToken.mockResolvedValue({ csrfToken: 'csrf-token' })
  })

  it('accepts a backend-authenticated password session without invoking WebAuthn', async () => {
    mocks.login.mockResolvedValue({ status: 'authenticated', user })

    const store = useAuthStore()
    const result = await store.login({ username: user.username, password: 'Password123!' })

    expect(result).toEqual(user)
    expect(store.isAuthenticated).toBe(true)
    expect(mocks.authenticateWithWebAuthn).not.toHaveBeenCalled()
    expect(mocks.verifyWebAuthnLogin).not.toHaveBeenCalled()
  })

  it('keeps the existing WebAuthn login flow when the backend requires it', async () => {
    const options = { challenge: 'challenge' }
    const credential = { id: 'credential-001' }
    mocks.login.mockResolvedValue({
      status: 'webauthn_required',
      pending_token: 'pending-token',
      options,
    })
    mocks.authenticateWithWebAuthn.mockResolvedValue(credential)
    mocks.verifyWebAuthnLogin.mockResolvedValue(user)

    const store = useAuthStore()
    await store.login({ username: user.username, password: 'Password123!' })

    expect(mocks.authenticateWithWebAuthn).toHaveBeenCalledWith(options)
    expect(mocks.verifyWebAuthnLogin).toHaveBeenCalledWith({
      pending_token: 'pending-token',
      credential,
    })
  })
})
