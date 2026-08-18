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
const WECHAT_IOS_MESSAGE = '当前在微信内置浏览器中，无法完成本人验证。请点击右上角“…”，选择“在 Safari 中打开”后重试'
const WECHAT_ANDROID_MESSAGE = '当前在微信内置浏览器中，无法完成本人验证。请点击右上角“…”，选择“在浏览器打开”后重试'
const NOT_ALLOWED_MESSAGE = '本人验证未完成：可能已取消、超时，或当前浏览器阻止了此次操作，请重试'
const NO_PASSKEY_MESSAGE = '当前设备未找到该账号已绑定的通行密钥，请使用原绑定设备，或联系管理员重新绑定'
const CREDENTIAL_MANAGER_MESSAGE =
  '手机通行密钥服务暂时不可用。请更新系统浏览器和通行密钥服务，确认已设置锁屏并启用密码管理器中的通行密钥后重试；仍失败时可选择其他手机或安全密钥'
const NO_COMPATIBLE_AUTHENTICATOR_MESSAGE =
  '当前电脑没有可用的 Windows Hello 或通行密钥设备。请先设置 Windows Hello PIN，或更新 Chrome/Edge 后选择手机或安全密钥重试'

export function getWebAuthnEnvironmentIssue(): string | undefined {
  if (typeof navigator !== 'undefined') {
    const userAgent = navigator.userAgent
    const isMobileWechat = /MicroMessenger/i.test(userAgent) && /Android|iPad|iPhone|iPod/i.test(userAgent)
    if (isMobileWechat) {
      return /iPad|iPhone|iPod/i.test(userAgent) ? WECHAT_IOS_MESSAGE : WECHAT_ANDROID_MESSAGE
    }
  }

  if (!browserSupportsWebAuthn()) {
    return UNSUPPORTED_MESSAGE
  }

  return undefined
}

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
  const environmentIssue = getWebAuthnEnvironmentIssue()
  if (environmentIssue) {
    throw new Error(environmentIssue)
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
  if (isNoPasskeyAvailable(error)) {
    return new Error(NO_PASSKEY_MESSAGE)
  }
  if (hasErrorMessage(error, /unknown error occurred while talking to the credential manager/i)) {
    return new Error(CREDENTIAL_MANAGER_MESSAGE)
  }
  if (
    hasErrorMessage(
      error,
      /device (?:can(?:not|'t)|cannot) be used (?:with|for) this site|website may need (?:to be )?updated|other type of device/i,
    )
  ) {
    return new Error(NO_COMPATIBLE_AUTHENTICATOR_MESSAGE)
  }
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
  if (code === 'ERROR_PASSTHROUGH_SEE_CAUSE_PROPERTY') {
    return new Error(getWebAuthnEnvironmentIssue() ?? NOT_ALLOWED_MESSAGE)
  }

  if (readErrorName(error) === 'NotAllowedError') {
    return new Error(getWebAuthnEnvironmentIssue() ?? NOT_ALLOWED_MESSAGE)
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

function readErrorName(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('name' in error)) {
    return undefined
  }

  const name = (error as { name: unknown }).name
  return typeof name === 'string' ? name : undefined
}

function isNoPasskeyAvailable(error: unknown): boolean {
  return hasErrorMessage(
    error,
    /no (?:matching )?(?:passkeys?|credentials?)(?: are)? available|credential.*not found/i,
  )
}

function hasErrorMessage(error: unknown, pattern: RegExp): boolean {
  return [readErrorMessage(error), readErrorMessage(readErrorCause(error))].some(
    (message) => typeof message === 'string' && pattern.test(message),
  )
}

function readErrorMessage(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('message' in error)) {
    return undefined
  }

  const message = (error as { message: unknown }).message
  return typeof message === 'string' ? message : undefined
}

function readErrorCause(error: unknown): unknown {
  if (typeof error !== 'object' || error === null || !('cause' in error)) {
    return undefined
  }

  return (error as { cause: unknown }).cause
}
