import { formatFileSize } from '@/shared/utils/format'

it('formats file sizes', () => {
  expect(formatFileSize(512)).toBe('512 B')
  expect(formatFileSize(2048)).toBe('2.00 KB')
  expect(formatFileSize(undefined)).toBe('-')
})
