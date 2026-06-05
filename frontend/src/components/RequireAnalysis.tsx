import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { hasActiveAnalysis } from '../lib/sessionKeys'

/** Post-analysis app pages — redirect to /analyze when no completed run in session. */
export default function RequireAnalysis({ children }: { children: ReactNode }) {
  const location = useLocation()

  if (!hasActiveAnalysis()) {
    return <Navigate to="/analyze" replace state={{ from: location.pathname }} />
  }

  return children
}
