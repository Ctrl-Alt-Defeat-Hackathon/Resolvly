import { useLayoutEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { consumePendingSectionScroll, scrollToPageTop, scrollToSection } from '../lib/pageScroll'

/** Reset window scroll on route change; smooth-scroll to hash targets on homepage. */
export default function ScrollToTop() {
  const { pathname, hash } = useLocation()

  useLayoutEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual'
    }
  }, [])

  useLayoutEffect(() => {
    const clearPending = consumePendingSectionScroll(150)
    if (clearPending) return clearPending

    const hashId = hash.replace(/^#/, '')
    if (pathname === '/' && hashId) {
      const timer = window.setTimeout(() => scrollToSection(hashId, 'smooth'), 80)
      return () => window.clearTimeout(timer)
    }

    scrollToPageTop('auto')
  }, [pathname, hash])

  return null
}
