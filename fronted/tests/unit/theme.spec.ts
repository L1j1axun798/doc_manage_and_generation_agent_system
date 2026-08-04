import { vi } from 'vitest'

import { setTheme, useTheme } from '@/shared/composables/useTheme'

describe('application theme', () => {
  afterEach(() => {
    setTheme('light')
    window.localStorage.removeItem('wind-doc-system.theme')
    document.documentElement.classList.remove('dark', 'theme-is-switching')
    vi.restoreAllMocks()
  })

  it('applies and persists the selected theme', () => {
    const { isDarkTheme, toggleTheme } = useTheme()

    setTheme('dark')

    expect(isDarkTheme.value).toBe(true)
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(window.localStorage.getItem('wind-doc-system.theme')).toBe('dark')

    toggleTheme()

    expect(isDarkTheme.value).toBe(false)
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('temporarily disables transitions while the theme is changing', () => {
    const animationFrames: FrameRequestCallback[] = []

    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      animationFrames.push(callback)
      return animationFrames.length
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => undefined)

    setTheme('light')
    setTheme('dark')

    expect(document.documentElement.classList.contains('theme-is-switching')).toBe(true)

    animationFrames.shift()?.(0)
    expect(document.documentElement.classList.contains('theme-is-switching')).toBe(true)

    animationFrames.shift()?.(16)
    expect(document.documentElement.classList.contains('theme-is-switching')).toBe(false)
  })
})
