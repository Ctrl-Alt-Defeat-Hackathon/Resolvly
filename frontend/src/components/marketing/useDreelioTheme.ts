import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'resolvly-dreelio-theme'

export type DreelioTheme = 'light' | 'dark'

function readStoredTheme(): DreelioTheme {
  if (typeof window === 'undefined') return 'light'
  return localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light'
}

export function useDreelioTheme() {
  const [theme, setTheme] = useState<DreelioTheme>(readStoredTheme)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, theme)
    document.body.dataset.dreelioTheme = theme
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggleTheme, isDark: theme === 'dark' }
}
