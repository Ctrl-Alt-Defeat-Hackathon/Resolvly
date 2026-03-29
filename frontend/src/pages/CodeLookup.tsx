import { Navigate } from 'react-router-dom'

/** Standalone URL redirects into Indiana Resources → Code lookup. */
export default function CodeLookup() {
  return <Navigate to="/indiana-resources/code-lookup" replace />
}
