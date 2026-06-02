import { useEffect, useState, type MouseEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import TransitionLink from './TransitionLink'
import { hashFromNavHref, useActiveSection } from './useActiveSection'
import { goToSection, scrollToPageTop } from '../../lib/pageScroll'
import { viewTransitionNavigate } from '../../lib/viewTransitionNavigate'

type NavLink = { t: string; href: string; sectionId?: string }

export default function DreelioNav({
  onStart,
  activePath,
}: {
  onStart: () => void
  activePath?: 'home' | 'resources'
}) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const onHome = pathname === '/'
  const activeSectionId = useActiveSection(['pipeline', 'features'], onHome)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const links: NavLink[] = [
    { t: 'How it works', href: '/#pipeline', sectionId: 'pipeline' },
    { t: 'Features', href: '/#features', sectionId: 'features' },
    { t: 'Resources', href: '/resources' },
  ]

  function handleLogoClick(e: MouseEvent<HTMLAnchorElement>) {
    e.preventDefault()
    if (pathname !== '/') {
      viewTransitionNavigate(navigate, '/')
      return
    }
    if (window.location.hash) {
      window.history.replaceState(null, '', '/')
    }
    scrollToPageTop('smooth')
  }

  function handleSectionClick(e: MouseEvent<HTMLAnchorElement>, href: string, sectionId?: string) {
    const id = sectionId ?? href.replace(/^\/?#/, '')
    if (!id) return
    e.preventDefault()
    goToSection(id, pathname, navigate)
  }

  function linkClass(href: string, sectionId?: string) {
    const hash = sectionId ?? hashFromNavHref(href)
    const isRouteActive = href === '/resources' && (activePath === 'resources' || pathname === '/resources')
    const isSectionActive = onHome && hash != null && activeSectionId === hash
    return ['nav-link', isRouteActive || isSectionActive ? 'is-active' : ''].filter(Boolean).join(' ')
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        display: 'flex',
        justifyContent: 'center',
        padding: scrolled ? '14px 16px' : '0',
        transition: 'padding .45s var(--ease)',
        pointerEvents: 'none',
      }}
    >
      <nav
        style={{
          pointerEvents: 'auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          maxWidth: scrolled ? 880 : 1320,
          height: scrolled ? 60 : 76,
          padding: scrolled ? '0 12px 0 24px' : '0 28px',
          borderRadius: scrolled ? 9999 : 0,
          background: scrolled ? 'rgba(251,248,241,0.72)' : 'rgba(239,232,219,0.0)',
          backdropFilter: scrolled ? 'blur(16px) saturate(1.4)' : 'none',
          WebkitBackdropFilter: scrolled ? 'blur(16px) saturate(1.4)' : 'none',
          border: scrolled ? '1px solid rgba(255,255,255,0.6)' : '1px solid transparent',
          boxShadow: scrolled ? 'var(--sh-lg)' : 'none',
          transition: 'all .45s var(--ease)',
        }}
      >
        <a
          href="/"
          onClick={handleLogoClick}
          style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none' }}
          aria-label="Resolvly home — scroll to top"
        >
          <span
            style={{
              width: 26,
              height: 26,
              borderRadius: 8,
              background: 'var(--accent)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: 16,
              letterSpacing: '-0.06em',
            }}
          >
            R
          </span>
          <span style={{ fontWeight: 800, fontSize: 21, color: 'var(--accent)', letterSpacing: '-0.045em' }}>
            Resolvly
          </span>
        </a>
        <div
          className="nav-links"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 30,
            position: 'absolute',
            left: '50%',
            transform: 'translateX(-50%)',
          }}
        >
          {links.map((l) =>
            l.href.startsWith('/#') ? (
              <a
                key={l.t}
                href={l.href}
                className={linkClass(l.href, l.sectionId)}
                onClick={(e) => handleSectionClick(e, l.href, l.sectionId)}
              >
                {l.t}
              </a>
            ) : (
              <TransitionLink key={l.t} to={l.href} className={linkClass(l.href, l.sectionId)}>
                {l.t}
              </TransitionLink>
            ),
          )}
        </div>
        <button
          type="button"
          className="btn btn-primary"
          style={{
            padding: '9px 18px',
            fontSize: 14,
            opacity: scrolled ? 1 : 0,
            transform: scrolled ? 'none' : 'translateX(12px)',
            pointerEvents: scrolled ? 'auto' : 'none',
            transition: 'opacity .4s var(--ease), transform .4s var(--ease)',
          }}
          onClick={onStart}
        >
          Start Free Analysis
        </button>
      </nav>
    </div>
  )
}
