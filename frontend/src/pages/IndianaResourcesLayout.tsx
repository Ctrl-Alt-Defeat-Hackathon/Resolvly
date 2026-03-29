import { Outlet, NavLink } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function IndianaResourcesLayout() {
  return (
    <div
      className="flex min-h-screen flex-col bg-background font-[Inter,sans-serif] text-on-background selection:bg-primary-container selection:text-white"
    >
      <Navbar />

      <main className="flex-1 px-6 pb-16 pt-20 md:px-12">
        <div className="mx-auto mb-8 max-w-6xl border-b border-slate-200 bg-background dark:border-slate-700">
          <nav
            className="no-scrollbar flex gap-0 overflow-x-auto"
            aria-label="Indiana Resources sections"
          >
            <NavLink
              to="/indiana-resources"
              end
              className={({ isActive }) =>
                `-mb-px whitespace-nowrap border-b-2 px-5 py-3 text-sm font-semibold transition-colors
                ${isActive ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'}`
              }
            >
              Resources hub
            </NavLink>
            <NavLink
              to="/indiana-resources/code-lookup"
              className={({ isActive }) =>
                `-mb-px whitespace-nowrap border-b-2 px-5 py-3 text-sm font-semibold transition-colors
                ${isActive ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'}`
              }
            >
              Code &amp; term lookup
            </NavLink>
          </nav>
        </div>

        <Outlet />
      </main>

      <Footer />
    </div>
  )
}
