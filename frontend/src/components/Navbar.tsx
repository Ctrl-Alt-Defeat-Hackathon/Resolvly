import { Link, useLocation, useNavigate } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'

// Pages shown only on the restricted pre-analysis pages (Landing + Upload)
const RESTRICTED_NAV = [
  { label: 'Landing Page', to: '/' },
  { label: 'Upload Wizard', to: '/upload-wizard' },
]

// Full nav shown once the user has reached the analysis flow
const FULL_NAV = [
  { label: 'Landing Page', to: '/' },
  { label: 'Upload Wizard', to: '/upload-wizard' },
  { label: 'Action Plan', to: '/action-plan' },
  { label: 'Appeal Drafting', to: '/appeal-drafting' },
  { label: 'Indiana Resources', to: '/indiana-resources' },
  { label: 'Code Lookup', to: '/code-lookup' },
]

const RESTRICTED_PATHS = ['/', '/upload-wizard']

export default function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()

  const isRestricted = RESTRICTED_PATHS.includes(pathname)
  const navLinks = isRestricted ? RESTRICTED_NAV : FULL_NAV

  return (
    <nav className="fixed top-0 z-50 w-full border-b border-slate-200/60 bg-white/90 shadow-sm backdrop-blur-md dark:border-slate-700/80 dark:bg-slate-950/92 dark:shadow-[0_1px_0_0_rgba(15,23,42,0.75)]">
      <div className="flex justify-between items-center px-8 h-16 max-w-full mx-auto">
        <Link
          to="/"
          className="font-headline text-2xl font-bold tracking-tighter text-sky-900 dark:text-sky-100"
        >
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
                    ? 'border-b-2 border-sky-900 pb-1 text-sky-900 transition-colors duration-200 dark:border-sky-300 dark:text-sky-100'
                    : 'text-slate-500 transition-colors duration-200 hover:text-sky-700 dark:text-slate-400 dark:hover:text-sky-300'
                }
              >
                {label}
              </Link>
            )
          })}
        </div>
        <div className="flex items-center gap-3 md:gap-4">
          <ThemeToggle />
          {isRestricted && pathname !== '/upload-wizard' && (
            <button
              onClick={() => navigate('/upload-wizard')}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-on-primary shadow-sm transition-all hover:opacity-90"
            >
              Get Started
            </button>
          )}
          <button
            type="button"
            className="text-sm font-medium text-sky-900 hover:opacity-80 dark:text-sky-100"
          >
            Sign In
          </button>
        </div>
      </div>
    </nav>
  )
}
