import { createContext, useContext, type ReactNode } from 'react'
import { useDreelioTheme, type DreelioTheme } from './useDreelioTheme'

type DreelioThemeContextValue = {
  theme: DreelioTheme
  isDark: boolean
  toggleTheme: () => void
}

const DreelioThemeContext = createContext<DreelioThemeContextValue | null>(null)

export function DreelioThemeProvider({ children }: { children: ReactNode }) {
  const value = useDreelioTheme()
  return <DreelioThemeContext.Provider value={value}>{children}</DreelioThemeContext.Provider>
}

export function useDreelioThemeContext() {
  const ctx = useContext(DreelioThemeContext)
  if (!ctx) throw new Error('useDreelioThemeContext must be used within DreelioThemeProvider')
  return ctx
}
