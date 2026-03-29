import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import UploadWizard from './pages/UploadWizard'
import ActionPlan from './pages/ActionPlan'
import CodeLookup from './pages/CodeLookup'
import AppealDrafting from './pages/AppealDrafting'
import IndianaResourcesLayout from './pages/IndianaResourcesLayout'
import IndianaResourcesHub from './pages/IndianaResourcesHub'
import CodeLookupContent from './pages/CodeLookupContent'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/upload-wizard" element={<UploadWizard />} />
        <Route path="/action-plan" element={<ActionPlan />} />
        <Route path="/code-lookup" element={<CodeLookup />} />
        <Route path="/appeal-drafting" element={<AppealDrafting />} />
        <Route path="/indiana-resources" element={<IndianaResourcesLayout />}>
          <Route index element={<IndianaResourcesHub />} />
          <Route path="code-lookup" element={<CodeLookupContent />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
