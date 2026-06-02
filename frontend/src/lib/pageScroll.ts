import type { NavigateFunction } from 'react-router-dom'
import { viewTransitionNavigate } from './viewTransitionNavigate'

export const PENDING_SECTION_KEY = 'resolvly-pending-section'

/** Scroll to a section by id with fixed-nav offset (requires scroll-margin-top on targets). */
export function scrollToSection(sectionId: string, behavior: ScrollBehavior = 'smooth') {
  const el = document.getElementById(sectionId)
  if (!el) return false
  el.scrollIntoView({ behavior, block: 'start' })
  return true
}

/** Scroll to the top of the page (hero `#top` when present). */
export function scrollToPageTop(behavior: ScrollBehavior = 'smooth') {
  const topEl = document.getElementById('top')
  if (topEl) {
    topEl.scrollIntoView({ behavior, block: 'start' })
    return
  }
  window.scrollTo({ top: 0, left: 0, behavior })
}

export function parseSectionIdFromHref(href: string): string | null {
  const match = href.match(/#([A-Za-z][\w-]*)/)
  return match?.[1] ?? null
}

/** Smooth-scroll to a homepage section; navigates home first when needed. */
export function goToSection(
  sectionId: string,
  pathname: string,
  navigate: NavigateFunction,
  options?: { useViewTransition?: boolean },
) {
  if (pathname === '/') {
    window.history.replaceState(null, '', `/#${sectionId}`)
    scrollToSection(sectionId, 'smooth')
    return
  }

  sessionStorage.setItem(PENDING_SECTION_KEY, sectionId)
  if (options?.useViewTransition !== false) {
    viewTransitionNavigate(navigate, '/')
  } else {
    navigate('/')
  }
}

export function consumePendingSectionScroll(delayMs = 120) {
  const pending = sessionStorage.getItem(PENDING_SECTION_KEY)
  if (!pending) return undefined

  sessionStorage.removeItem(PENDING_SECTION_KEY)
  const timer = window.setTimeout(() => scrollToSection(pending, 'smooth'), delayMs)
  return () => window.clearTimeout(timer)
}
