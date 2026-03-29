import { useTheme } from '../context/theme-context'

/** Shows sun in dark mode (click → light) and moon in light mode (click → dark). */
export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200/80 bg-white/90 text-sky-900 shadow-sm transition-colors hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800/90 dark:text-sky-100 dark:hover:bg-slate-700"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={isDark}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      <span
        className="material-symbols-outlined text-[20px]"
        style={{ fontVariationSettings: isDark ? "'FILL' 1" : "'FILL' 0" }}
      >
        {isDark ? 'light_mode' : 'dark_mode'}
      </span>
    </button>
  )
}
