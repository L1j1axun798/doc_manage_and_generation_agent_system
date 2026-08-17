import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PublicKeyCredentialCreationOptionsJSON } from '@simplewebauthn/browser'

const mocks = vi.hoisted(() => ({
  browserSupportsWebAuthn: vi.fn(() => true),
  startAuthentication: vi.fn(),
  startRegistration: vi.fn(),
}))

vi.mock('@simplewebauthn/browser', () => ({
  browserSupportsWebAuthn: mocks.browserSupportsWebAuthn,
  startAuthentication: mocks.startAuthentication,
  startRegistration: mocks.startRegistration,
}))

import {
  getWebAuthnEnvironmentIssue,
  registerWithWebAuthn,
} from '@/modules/auth/services/webauthn'

const registrationOptions = {
  challenge: 'challenge',
  rp: { id: 'localhost', name: 'Example' },
  user: { id: 'user-id', name: 'operator', displayName: 'Operator' },
  pubKeyCredParams: [{ alg: -7, type: 'public-key' as const }],
} as PublicKeyCredentialCreationOptionsJSON

describe('WebAuthn browser error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.browserSupportsWebAuthn.mockReturnValue(true)
    vi.stubGlobal('navigator', {
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit Safari',
    })
  })

  it('blocks mobile WeChat before starting credential registration', async () => {
    vi.stubGlobal('navigator', {
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) MicroMessenger/8.0.50',
    })

    expect(getWebAuthnEnvironmentIssue()).toContain('微信内置浏览器')
    expect(getWebAuthnEnvironmentIssue()).toContain('Safari')
    await expect(registerWithWebAuthn(registrationOptions)).rejects.toThrow('在 Safari 中打开')
    expect(mocks.startRegistration).not.toHaveBeenCalled()
  })

  it('localizes SimpleWebAuthn passthrough NotAllowedError messages', async () => {
    const error = Object.assign(
      new Error('The request is not allowed by the user agent or the platform in the current context'),
      {
        code: 'ERROR_PASSTHROUGH_SEE_CAUSE_PROPERTY',
        name: 'NotAllowedError',
      },
    )
    mocks.startRegistration.mockRejectedValue(error)

    await expect(registerWithWebAuthn(registrationOptions)).rejects.toThrow('本人验证未完成')
  })

  it('reports unsupported browsers before starting credential registration', async () => {
    mocks.browserSupportsWebAuthn.mockReturnValue(false)

    expect(getWebAuthnEnvironmentIssue()).toContain('不支持本人验证')
    await expect(registerWithWebAuthn(registrationOptions)).rejects.toThrow('不支持本人验证')
    expect(mocks.startRegistration).not.toHaveBeenCalled()
  })
})
