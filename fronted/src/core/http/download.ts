const FILENAME_STAR_PATTERN = /filename\*=UTF-8''([^;]+)/
const FILENAME_PATTERN = /filename="?([^"]+)"?/

export function getFilenameFromContentDisposition(header: string | null): string | null {
  if (!header) {
    return null
  }

  const encoded = FILENAME_STAR_PATTERN.exec(header)?.[1]
  if (encoded) {
    return decodeURIComponent(encoded)
  }

  return FILENAME_PATTERN.exec(header)?.[1] || null
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
