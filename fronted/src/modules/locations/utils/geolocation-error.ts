const INSECURE_ORIGIN_MESSAGE =
  '浏览器要求使用 HTTPS 或 localhost 访问后才能定位；当前访问地址不是安全源'

function extractErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message?: unknown }).message || '').trim()
  }
  return ''
}

export function isInsecureGeolocationContext(): boolean {
  return typeof window !== 'undefined' && window.isSecureContext === false
}

export function normalizeGeolocationErrorMessage(error: unknown): string {
  const message = extractErrorMessage(error)
  if (/only secure origins are allowed/i.test(message)) {
    return INSECURE_ORIGIN_MESSAGE
  }

  if (error && typeof error === 'object' && 'code' in error) {
    const code = Number((error as { code?: unknown }).code)
    if (code === 1) {
      return '用户拒绝定位授权'
    }
    if (code === 2) {
      return '设备暂时无法获取位置'
    }
    if (code === 3) {
      return '定位超时，请到室外或稍后重试'
    }
  }

  return message || '浏览器定位失败'
}

export { INSECURE_ORIGIN_MESSAGE }
