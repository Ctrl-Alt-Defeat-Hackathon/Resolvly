import { useState, useEffect, type MouseEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { clearAllOutputsCache } from '../lib/outputsCache'
import { clearAnalysisSession, hasActiveAnalysis } from '../lib/sessionKeys'

type NavItem = { label: string; to: string; icon: string; short: string }

const APP_NAV: NavItem[] = [
  { label: 'Action Plan',       to: '/action-plan',       icon: 'assignment',    short: 'Plan'    },
  { label: 'Appeal Drafting',   to: '/appeal-drafting',   icon: 'edit_document', short: 'Appeal'  },
  { label: 'Indiana Resources', to: '/indiana-resources', icon: 'library_books', short: 'Indiana' },
  { label: 'Code Lookup',       to: '/code-lookup',       icon: 'search',        short: 'Codes'   },
]

function isNavActive(pathname: string, to: string): boolean {
  return pathname === to || pathname.startsWith(`${to}/`)
}

export default function AppNav() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [scrolled, setScrolled] = useState(false)
  const [showLeaveWarning, setShowLeaveWarning] = useState(false)
  const needsLeaveConfirm = hasActiveAnalysis()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  function requestLeaveHome() {
    setShowLeaveWarning(true)
  }

  function confirmLeaveHome() {
    clearAnalysisSession()
    clearAllOutputsCache()
    setShowLeaveWarning(false)
    navigate('/')
  }

  function handleLogoClick(e: MouseEvent<HTMLAnchorElement>) {
    if (!needsLeaveConfirm) return
    e.preventDefault()
    requestLeaveHome()
  }

  const backToHomeBtn = needsLeaveConfirm ? (
    <button
      type="button"
      onClick={requestLeaveHome}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '7px 16px',
        borderRadius: 999,
        border: '1.5px solid var(--accent)',
        background: 'transparent',
        color: 'var(--accent)',
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
        flexShrink: 0,
        whiteSpace: 'nowrap',
      }}
    >
      ← Back to Home
    </button>
  ) : (
    <Link
      to="/"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '7px 16px',
        borderRadius: 999,
        border: '1.5px solid var(--accent)',
        background: 'transparent',
        color: 'var(--accent)',
        fontSize: 13,
        fontWeight: 600,
        textDecoration: 'none',
        flexShrink: 0,
        whiteSpace: 'nowrap',
      }}
    >
      ← Back to Home
    </Link>
  )

  return (
    <>
      {/* Shell — same pattern as DreelioNav's dreelio-nav-shell */}
      <div
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
        <nav
          className={['dreelio-nav-bar', scrolled ? 'is-scrolled' : ''].filter(Boolean).join(' ')}
          style={{ pointerEvents: 'auto' }}
        >
          {/* Logo — same leave warning as Back to Home when analysis is active */}
          <Link className="nav-logo" to="/" onClick={handleLogoClick} aria-label="Resolvly home">
            <span className="nav-logo-mark">R</span>
            <span className="nav-logo-word">Resolvly</span>
          </Link>

          {/* App tabs */}
          <div className="nav-links nav-links-desktop app-nav-tabs">
            {APP_NAV.map(({ label, to }) => {
              const isActive = isNavActive(pathname, to)
              return (
                <Link
                  key={to}
                  to={to}
                  className={['nav-link', isActive ? 'is-active' : ''].filter(Boolean).join(' ')}
                >
                  {label}
                </Link>
              )
            })}
          </div>

          {/* Back to Home */}
          {backToHomeBtn}
        </nav>
      </div>

      {/* Mobile bottom nav */}
      <nav
        className="app-mobile-bottom-nav"
        aria-label="Main navigation"
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 50,
          background: 'var(--canvas)',
          borderTop: '1px solid var(--line)',
          height: 60,
        }}
      >
        <div style={{ display: 'flex', height: '100%' }}>
          {APP_NAV.map(({ to, icon, short }) => {
            const isActive = isNavActive(pathname, to)
            return (
              <Link
                key={to}
                to={to}
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 2,
                  color: isActive ? 'var(--accent)' : 'var(--ink-3)',
                  textDecoration: 'none',
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{
                    fontSize: 22,
                    fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0",
                  }}
                >
                  {icon}
                </span>
                {short}
              </Link>
            )
          })}
        </div>
      </nav>

      {/* Leave confirmation dialog */}
      {showLeaveWarning && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            background: 'rgba(0,0,0,0.4)',
            backdropFilter: 'blur(4px)',
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="leave-home-title"
        >
          <div
            style={{
              width: '100%',
              maxWidth: 440,
              borderRadius: 20,
              background: '#fff',
              border: '1px solid var(--line)',
              padding: 28,
              boxShadow: 'var(--sh-xl)',
            }}
          >
            <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'flex-start' }}>
              <span className="material-symbols-outlined" style={{ color: '#d97706', fontSize: 28, flexShrink: 0 }}>warning</span>
              <div>
                <h2 id="leave-home-title" style={{ fontWeight: 800, fontSize: 17, color: 'var(--accent)', marginBottom: 8 }}>
                  Leave and reset analysis?
                </h2>
                <p style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.65 }}>
                  Going back to the home page will clear your current claim analysis, uploaded document
                  context, and generated summaries from this session. You will need to run a new analysis
                  to see results again.
                </p>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                onClick={() => setShowLeaveWarning(false)}
                style={{
                  padding: '8px 18px',
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--ink)',
                  background: 'transparent',
                  border: '1.5px solid var(--line)',
                  borderRadius: 999,
                  cursor: 'pointer',
                }}
              >
                Stay on this page
              </button>
              <button
                type="button"
                onClick={confirmLeaveHome}
                style={{
                  padding: '8px 18px',
                  fontSize: 13,
                  fontWeight: 700,
                  color: '#fff',
                  background: 'var(--accent)',
                  border: 'none',
                  borderRadius: 999,
                  cursor: 'pointer',
                }}
              >
                Leave &amp; reset
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
