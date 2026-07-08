import {
  browserSupportsWebAuthn,
  startAuthentication,
  startRegistration,
  type AuthenticationResponseJSON,
  type PublicKeyCredentialCreationOptionsJSON,
  type PublicKeyCredentialRequestOptionsJSON,
  type RegistrationResponseJSON,
} from '@simplewebauthn/browser'

const UNSUPPORTED_MESSAGE = '当前浏览器或访问环境不支持本人验证，请使用支持 WebAuthn 的安全浏览器'
const CANONICAL_LOCAL_ORIGIN = 'http://localhost:5174'

export async function authenticateWithWebAuthn(
  options: PublicKeyCredentialRequestOptionsJSON,
): Promise<AuthenticationResponseJSON> {
  ensureWebAuthnSupported()
  ensureRpIdMatchesCurrentHost(options.rpId)

  try {
    return await startAuthentication({ optionsJSON: options })
  } catch (error) {
    throw toWebAuthnUserError(error)
  }
}

export async function registerWithWebAuthn(
  options: PublicKeyCredentialCreationOptionsJSON,
): Promise<RegistrationResponseJSON> {
  ensureWebAuthnSupported()
  ensureRpIdMatchesCurrentHost(options.rp.id)

  try {
    return await startRegistration({ optionsJSON: options })
  } catch (error) {
    throw toWebAuthnUserError(error)
  }
}

function ensureWebAuthnSupported(): void {
  if (!browserSupportsWebAuthn()) {
    throw new Error(UNSUPPORTED_MESSAGE)
  }
}

function ensureRpIdMatchesCurrentHost(rpId: string | undefined): void {
  if (!rpId || typeof window === 'undefined') {
    return
  }

  const hostname = window.location.hostname
  if (hostname === rpId || hostname.endsWith(`.${rpId}`)) {
    return
  }

  if (rpId === 'localhost') {
    throw new Error(`本人验证域名不匹配，请使用 ${CANONICAL_LOCAL_ORIGIN} 访问系统`)
  }

  throw new Error(`本人验证域名不匹配：当前访问域名 ${hostname} 与系统配置 ${rpId} 不一致`)
}

function toWebAuthnUserError(error: unknown): Error {
  const code = readErrorCode(error)
  if (code === 'ERROR_INVALID_RP_ID' || code === 'ERROR_INVALID_DOMAIN') {
    return new Error(`本人验证域名不匹配，请使用 ${CANONICAL_LOCAL_ORIGIN} 访问系统`)
  }
  if (code === 'ERROR_CEREMONY_ABORTED') {
    return new Error('本人验证已取消，请重新发起验证')
  }
  if (code === 'ERROR_AUTHENTICATOR_MISSING_USER_VERIFICATION_SUPPORT') {
    return new Error('当前设备未开启 Windows Hello 或不支持本人验证')
  }
  if (code === 'ERROR_AUTHENTICATOR_PREVIOUSLY_REGISTERED') {
    return new Error('当前设备已经绑定过本人验证')
  }
  if (code === 'ERROR_AUTHENTICATOR_GENERAL_ERROR') {
    return new Error('本人验证设备处理失败，请确认使用的是已绑定设备')
  }

  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    return new Error('本人验证未完成或已取消，请重新验证')
  }
  if (error instanceof Error && error.message.trim()) {
    return error
  }
  return new Error('本人验证失败')
}

function readErrorCode(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('code' in error)) {
    return undefined
  }

  const code = (error as { code: unknown }).code
  return typeof code === 'string' ? code : undefined
}
