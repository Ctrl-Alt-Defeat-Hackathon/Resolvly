import { Outlet } from 'react-router-dom'
import '../styles/dreelio-landing.css'
import AppNav from '../components/AppNav'
import DreelioFooter from '../components/marketing/DreelioFooter'

export default function IndianaResourcesLayout() {
  return (
    <div className="dreelio-landing min-h-screen flex flex-col" style={{ background: 'var(--canvas)', color: 'var(--ink)', fontFamily: 'var(--font)' }}>
      <AppNav />

      <main className="flex-1 pt-24 pb-24 md:pb-12">
        <div className="editorial-margin">
          <Outlet />
        </div>
      </main>

      <DreelioFooter />
    </div>
  )
}
