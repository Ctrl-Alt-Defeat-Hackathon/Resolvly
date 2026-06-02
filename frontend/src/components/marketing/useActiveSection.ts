import { useEffect, useState } from 'react'

const NAV_OFFSET = 100

/** Highlights nav items while their `id` sections are in view (homepage scroll spy). */
export function useActiveSection(sectionIds: string[], enabled: boolean) {
  const [activeId, setActiveId] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setActiveId(null)
      return
    }

    const elements = sectionIds
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => !!el)

    if (!elements.length) return

    const update = () => {
      const marker = window.scrollY + NAV_OFFSET
      let current: string | null = null

      for (const el of elements) {
        const top = el.offsetTop
        if (top <= marker) current = el.id
      }

      setActiveId(current)
    }

    update()
    const t = window.setTimeout(update, 120)
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    window.addEventListener('hashchange', update)
    return () => {
      window.clearTimeout(t)
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
      window.removeEventListener('hashchange', update)
    }
  }, [sectionIds, enabled])

  return activeId
}

export function hashFromNavHref(href: string): string | null {
  const hashIdx = href.indexOf('#')
  if (hashIdx === -1) return null
  return href.slice(hashIdx + 1) || null
}
