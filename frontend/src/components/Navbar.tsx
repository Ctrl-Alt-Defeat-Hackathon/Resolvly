import { Link, useLocation, useNavigate } from 'react-router-dom'

// Pages shown only on the restricted pre-analysis pages (landing + analyze)
const RESTRICTED_NAV: Array<{ label: string; to: string }> = []

// Full nav shown once the user has reached the analysis flow
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

  const isRestricted = RESTRICTED_PATHS.includes(pathname)
  const navLinks = isRestricted ? RESTRICTED_NAV : FULL_NAV

  return (
    <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-slate-200/50 shadow-sm">
      <div className="flex justify-between items-center px-8 h-16 max-w-full mx-auto">
        <Link to="/" className="text-2xl font-bold tracking-tighter text-sky-900 font-headline">
          Resolvly
        </Link>
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
        <div className="flex items-center gap-4">
          {isRestricted && pathname !== '/analyze' && (
            <button
              onClick={() => navigate('/analyze')}
              className="px-4 py-2 bg-primary text-white text-sm font-bold rounded-lg shadow-sm hover:opacity-90 transition-all"
            >
              Get Started
            </button>
          )}
        </div>
      </div>
    </nav>
  )
}
