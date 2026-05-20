import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { clearAllOutputsCache } from '../lib/outputsCache'
import { clearAnalysisSession, hasActiveAnalysis } from '../lib/sessionKeys'

const RESTRICTED_NAV: Array<{ label: string; to: string }> = []

const FULL_NAV = [
  { label: 'Action Plan', to: '/action-plan' },
  { label: 'Appeal Drafting', to: '/appeal-drafting' },
  { label: 'Indiana Resources', to: '/indiana-resources' },
  { label: 'Code Lookup', to: '/code-lookup' },
]

const RESTRICTED_PATHS = ['/', '/analyze']

export default function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [showLeaveWarning, setShowLeaveWarning] = useState(false)

  const isRestricted = RESTRICTED_PATHS.includes(pathname)
  const navLinks = isRestricted ? RESTRICTED_NAV : FULL_NAV
  const needsLeaveConfirm = !isRestricted && hasActiveAnalysis()

  function requestLeaveHome() {
    setShowLeaveWarning(true)
  }

  function confirmLeaveHome() {
    clearAnalysisSession()
    clearAllOutputsCache()
    setShowLeaveWarning(false)
    navigate('/')
  }

  return (
    <>
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-slate-200/50 shadow-sm">
        <div className="flex justify-between items-center px-8 h-16 max-w-full mx-auto">
          {needsLeaveConfirm ? (
            <button
              type="button"
              onClick={requestLeaveHome}
              className="text-2xl font-bold tracking-tighter text-sky-900 font-headline hover:opacity-80 transition-opacity"
            >
              Resolvly
            </button>
          ) : (
            <Link to="/" className="text-2xl font-bold tracking-tighter text-sky-900 font-headline">
              Resolvly
            </Link>
          )}
          <div className="hidden md:flex items-center gap-8 text-sm font-medium tracking-wide">
            {navLinks.map(({ label, to }) => {
              const isActive = pathname === to
              return (
                <Link
                  key={to}
                  to={to}
                  className={
                    isActive
                      ? 'text-sky-900 border-b-2 border-sky-900 pb-1 transition-colors duration-200'
                      : 'text-slate-500 hover:text-sky-700 transition-colors duration-200'
                  }
                >
                  {label}
                </Link>
              )
            })}
          </div>
          <div className="flex items-center gap-3">
            {needsLeaveConfirm && (
              <button
                type="button"
                onClick={requestLeaveHome}
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-semibold text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 hover:text-sky-900 transition-colors"
              >
                <span className="material-symbols-outlined text-[18px]">home</span>
                <span className="hidden sm:inline">Back to Home</span>
              </button>
            )}
            {isRestricted && pathname !== '/analyze' && (
              <button
                type="button"
                onClick={() => navigate('/analyze')}
                className="px-4 py-2 bg-primary text-white text-sm font-bold rounded-lg shadow-sm hover:opacity-90 transition-all"
              >
                Get Started
              </button>
            )}
          </div>
        </div>
      </nav>

      {showLeaveWarning && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="leave-home-title"
        >
          <div className="w-full max-w-md rounded-xl bg-white shadow-xl border border-slate-200 p-6">
            <div className="flex items-start gap-3 mb-4">
              <span className="material-symbols-outlined text-amber-600 text-3xl shrink-0">warning</span>
              <div>
                <h2 id="leave-home-title" className="text-lg font-bold font-headline text-slate-900">
                  Leave and reset analysis?
                </h2>
                <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                  Going back to the home page will clear your current claim analysis, uploaded document
                  context, and generated summaries from this session. You will need to run a new analysis
                  to see results again.
                </p>
              </div>
            </div>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowLeaveWarning(false)}
                className="px-4 py-2.5 text-sm font-semibold text-slate-700 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
              >
                Stay on this page
              </button>
              <button
                type="button"
                onClick={confirmLeaveHome}
                className="px-4 py-2.5 text-sm font-bold text-white rounded-lg bg-primary hover:opacity-90 transition-opacity"
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
