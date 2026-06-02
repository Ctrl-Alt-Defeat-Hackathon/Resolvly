import { useEffect, useState, type MouseEvent, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import TransitionLink from './TransitionLink'
import { hashFromNavHref, useActiveSection } from './useActiveSection'
import { goToSection, scrollToPageTop } from '../../lib/pageScroll'
import { viewTransitionNavigate } from '../../lib/viewTransitionNavigate'

type NavLink = { t: string; href: string; sectionId?: string }

function NavLogo({
  onClick,
  className = '',
}: {
  onClick?: (e: MouseEvent<HTMLAnchorElement>) => void
  className?: string
}) {
  return (
    <a
      href="/"
      onClick={onClick}
      className={['nav-logo', className].filter(Boolean).join(' ')}
      aria-label="Resolvly home — scroll to top"
    >
      <span className="nav-logo-mark">R</span>
      <span className="nav-logo-word">Resolvly</span>
    </a>
  )
}

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
  const [menuOpen, setMenuOpen] = useState(false)
  const onHome = pathname === '/'
  const activeSectionId = useActiveSection(['pipeline', 'features'], onHome)

  const links: NavLink[] = [
    { t: 'How it works', href: '/#pipeline', sectionId: 'pipeline' },
    { t: 'Features', href: '/#features', sectionId: 'features' },
    { t: 'Resources', href: '/resources' },
  ]

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    setMenuOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!menuOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [menuOpen])

  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  function closeMenu() {
    setMenuOpen(false)
  }

  function handleLogoClick(e: MouseEvent<HTMLAnchorElement>) {
    e.preventDefault()
    closeMenu()
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
    closeMenu()
    goToSection(id, pathname, navigate)
  }

  function linkClass(href: string, sectionId?: string, mobile = false) {
    const hash = sectionId ?? hashFromNavHref(href)
    const isRouteActive = href === '/resources' && (activePath === 'resources' || pathname === '/resources')
    const isSectionActive = onHome && hash != null && activeSectionId === hash
    return ['nav-link', mobile ? 'nav-link-mobile' : '', isRouteActive || isSectionActive ? 'is-active' : '']
      .filter(Boolean)
      .join(' ')
  }

  function renderLink(l: NavLink, mobile = false) {
    if (l.href.startsWith('/#')) {
      return (
        <a
          key={l.t}
          href={l.href}
          className={linkClass(l.href, l.sectionId, mobile)}
          onClick={(e) => handleSectionClick(e, l.href, l.sectionId)}
        >
          {l.t}
        </a>
      )
    }
    return (
      <TransitionLink
        key={l.t}
        to={l.href}
        className={linkClass(l.href, l.sectionId, mobile)}
        onClick={mobile ? closeMenu : undefined}
      >
        {l.t}
      </TransitionLink>
    )
  }

  const barClass = ['dreelio-nav-bar', scrolled ? 'is-scrolled' : '', menuOpen ? 'is-menu-open' : '']
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={['dreelio-nav-shell', menuOpen ? 'is-menu-open' : ''].filter(Boolean).join(' ')}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: scrolled ? '14px 16px 0' : '0',
        transition: 'padding .45s var(--ease)',
        pointerEvents: 'none',
      }}
    >
      {menuOpen ? (
        <button
          type="button"
          className="mobile-nav-backdrop"
          aria-label="Close menu"
          onClick={closeMenu}
        />
      ) : null}

      <nav className={barClass} style={{ pointerEvents: 'auto' }}>
        <NavLogo onClick={handleLogoClick} />

        <div className="nav-links nav-links-desktop">
          {links.map((l) => renderLink(l))}
        </div>

        <button
          type="button"
          className="btn btn-primary nav-desktop-cta"
          style={{
            padding: scrolled ? '9px 18px' : '11px 22px',
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

        <button
          type="button"
          className="nav-mobile-toggle"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className={`nav-menu-icon${menuOpen ? ' is-open' : ''}`} aria-hidden>
            <span />
            <span />
          </span>
        </button>
      </nav>

      {menuOpen ? (
        <MobileMenuStack links={links} renderLink={renderLink} onStart={onStart} onClose={closeMenu} />
      ) : null}
    </div>
  )
}

function MobileMenuStack({
  links,
  renderLink,
  onStart,
  onClose,
}: {
  links: NavLink[]
  renderLink: (l: NavLink, mobile?: boolean) => ReactNode
  onStart: () => void
  onClose: () => void
}) {
  return (
    <div className="mobile-nav-stack" style={{ pointerEvents: 'auto' }}>
      <div className="mobile-nav-card">
        <nav className="mobile-nav-links" aria-label="Mobile navigation">
          {links.map((l) => renderLink(l, true))}
        </nav>
      </div>
      <button
        type="button"
        className="btn btn-primary mobile-nav-cta"
        onClick={() => {
          onClose()
          onStart()
        }}
      >
        Start Free Analysis
        <span className="ms arrow" style={{ fontSize: 19 }}>arrow_forward</span>
      </button>
    </div>
  )
}
