import { computed, readonly, ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const THEME_STORAGE_KEY = 'wind-doc-system.theme'
const ELEMENT_PLUS_DARK_CLASS = 'dark'
const THEME_SWITCHING_CLASS = 'theme-is-switching'
const themeMode = ref<ThemeMode>('light')
let initialized = false
let transitionCleanupFrame: number | null = null

function getStoredTheme(): ThemeMode | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
    return storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : null
  } catch {
    return null
  }
}

function scheduleTransitionCleanup(root: HTMLElement): void {
  const view = root.ownerDocument.defaultView

  if (view === null || typeof view.requestAnimationFrame !== 'function') {
    root.classList.remove(THEME_SWITCHING_CLASS)
    return
  }

  if (transitionCleanupFrame !== null) {
    view.cancelAnimationFrame(transitionCleanupFrame)
  }

  transitionCleanupFrame = view.requestAnimationFrame(() => {
    transitionCleanupFrame = view.requestAnimationFrame(() => {
      root.classList.remove(THEME_SWITCHING_CLASS)
      transitionCleanupFrame = null
    })
  })
}

function applyTheme(mode: ThemeMode, guardTransition = false): void {
  if (typeof document === 'undefined') {
    return
  }

  const root = document.documentElement
  const themeChanged = root.dataset.theme !== undefined && root.dataset.theme !== mode

  if (guardTransition && themeChanged) {
    root.classList.add(THEME_SWITCHING_CLASS)
  }

  root.dataset.theme = mode
  root.classList.toggle(ELEMENT_PLUS_DARK_CLASS, mode === 'dark')
  root.style.colorScheme = mode

  if (guardTransition && themeChanged) {
    scheduleTransitionCleanup(root)
  }
}

export function initializeTheme(): ThemeMode {
  if (!initialized) {
    themeMode.value = getStoredTheme() ?? 'light'
    initialized = true
  }

  applyTheme(themeMode.value)
  return themeMode.value
}

export function setTheme(mode: ThemeMode): void {
  themeMode.value = mode
  initialized = true
  applyTheme(mode, true)

  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    // Theme switching remains functional when persistent storage is unavailable.
  }
}

export function useTheme() {
  initializeTheme()

  const isDarkTheme = computed(() => themeMode.value === 'dark')

  function toggleTheme(): void {
    setTheme(isDarkTheme.value ? 'light' : 'dark')
  }

  return {
    themeMode: readonly(themeMode),
    isDarkTheme,
    toggleTheme,
    setTheme,
  }
}
