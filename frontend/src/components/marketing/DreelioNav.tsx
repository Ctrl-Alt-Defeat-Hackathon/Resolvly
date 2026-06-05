import { useEffect, useState, type MouseEvent, type ReactNode } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import TransitionLink from './TransitionLink'
import { hashFromNavHref, useActiveSection } from './useActiveSection'
import { goToSection, scrollToPageTop } from '../../lib/pageScroll'
import { viewTransitionNavigate } from '../../lib/viewTransitionNavigate'
import LeaveAnalysisDialog from './LeaveAnalysisDialog'

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
  appMode = false,
  confirmLeaveHome = false,
  onConfirmLeaveHome,
}: {
  onStart?: () => void
  activePath?: 'home' | 'resources'
  appMode?: boolean
  /** When true, logo / back-to-home triggers the leave-analysis dialog instead of navigating immediately. */
  confirmLeaveHome?: boolean
  onConfirmLeaveHome?: () => void
}) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [showLeaveWarning, setShowLeaveWarning] = useState(false)
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

  function requestLeaveHome() {
    if (confirmLeaveHome && onConfirmLeaveHome) {
      setShowLeaveWarning(true)
      return
    }
    goHome()
  }

  function goHome() {
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

  function handleLogoClick(e: MouseEvent<HTMLAnchorElement>) {
    e.preventDefault()
    requestLeaveHome()
  }

  function confirmLeaveHomeAction() {
    setShowLeaveWarning(false)
    closeMenu()
    if (onConfirmLeaveHome) {
      onConfirmLeaveHome()
      return
    }
    goHome()
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
    <>
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

        {appMode ? (
          confirmLeaveHome ? (
            <button
              type="button"
              className="nav-desktop-cta"
              onClick={requestLeaveHome}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--accent)',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: '9px 0',
                opacity: 1,
              }}
            >
              ← Back to Home
            </button>
          ) : (
            <Link
              to="/"
              className="nav-desktop-cta"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--accent)',
                textDecoration: 'none',
                padding: '9px 0',
                opacity: 1,
                transition: 'opacity .2s',
              }}
            >
              ← Back to Home
            </Link>
          )
        ) : (
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
        )}

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
        <MobileMenuStack
          links={links}
          renderLink={renderLink}
          onStart={onStart}
          onClose={closeMenu}
          appMode={appMode}
          onRequestLeaveHome={requestLeaveHome}
          confirmLeaveHome={confirmLeaveHome}
        />
      ) : null}
      </div>

      <LeaveAnalysisDialog
        open={showLeaveWarning}
        onStay={() => setShowLeaveWarning(false)}
        onLeave={confirmLeaveHomeAction}
      />
    </>
  )
}

function MobileMenuStack({
  links,
  renderLink,
  onStart,
  onClose,
  appMode = false,
  confirmLeaveHome = false,
  onRequestLeaveHome,
}: {
  links: NavLink[]
  renderLink: (l: NavLink, mobile?: boolean) => ReactNode
  onStart?: () => void
  onClose: () => void
  appMode?: boolean
  confirmLeaveHome?: boolean
  onRequestLeaveHome?: () => void
}) {
  return (
    <div className="mobile-nav-stack" style={{ pointerEvents: 'auto' }}>
      <div className="mobile-nav-card">
        <nav className="mobile-nav-links" aria-label="Mobile navigation">
          {links.map((l) => renderLink(l, true))}
        </nav>
      </div>
      {appMode ? (
        confirmLeaveHome ? (
          <button
            type="button"
            className="btn mobile-nav-cta"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              background: 'transparent',
              border: '2px solid var(--accent)',
              color: 'var(--accent)',
              fontWeight: 700,
            }}
            onClick={() => {
              onClose()
              onRequestLeaveHome?.()
            }}
          >
            ← Back to Home
          </button>
        ) : (
          <Link
            to="/"
            className="btn mobile-nav-cta"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              background: 'transparent',
              border: '2px solid var(--accent)',
              color: 'var(--accent)',
              fontWeight: 700,
              textDecoration: 'none',
            }}
            onClick={onClose}
          >
            ← Back to Home
          </Link>
        )
      ) : (
        <button
          type="button"
          className="btn btn-primary mobile-nav-cta"
          onClick={() => {
            onClose()
            onStart?.()
          }}
        >
          Start Free Analysis
          <span className="ms arrow" style={{ fontSize: 19 }}>arrow_forward</span>
        </button>
      )}
    </div>
  )
}
