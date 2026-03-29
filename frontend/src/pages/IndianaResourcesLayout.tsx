import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

export default function IndianaResourcesLayout() {
  return (
    <div
      className="bg-background text-on-background selection:bg-secondary-container min-h-screen flex flex-col"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      <Navbar />

      <main className="flex-1 pt-24 pb-12">
        <div className="editorial-margin">
          <Outlet />
        </div>
      </main>

      <Footer />
    </div>
  )
}
