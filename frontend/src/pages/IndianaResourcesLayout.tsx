import { Outlet, NavLink } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function IndianaResourcesLayout() {
  return (
    <div
      className="text-on-background selection:bg-primary-container selection:text-white min-h-screen flex flex-col"
      style={{ fontFamily: "'Inter', sans-serif", backgroundColor: '#f8f9fa' }}
    >
      <Navbar />

      <main className="flex-1 pt-20 pb-16 px-6 md:px-12">
        <div className="max-w-6xl mx-auto border-b border-slate-200 mb-8">
          <nav className="flex gap-0 overflow-x-auto no-scrollbar" aria-label="Indiana Resources sections">
            <NavLink
              to="/indiana-resources"
              end
              className={({ isActive }) =>
                `px-5 py-3 text-sm font-semibold whitespace-nowrap border-b-2 -mb-px transition-colors
                ${isActive ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'}`
              }
            >
              Resources hub
            </NavLink>
            <NavLink
              to="/indiana-resources/code-lookup"
              className={({ isActive }) =>
                `px-5 py-3 text-sm font-semibold whitespace-nowrap border-b-2 -mb-px transition-colors
                ${isActive ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'}`
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
