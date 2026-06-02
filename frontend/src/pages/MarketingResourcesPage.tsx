import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { viewTransitionNavigate } from '../lib/viewTransitionNavigate'
import '../styles/dreelio-landing.css'
import DreelioNav from '../components/marketing/DreelioNav'
import DreelioFooter from '../components/marketing/DreelioFooter'
import { DreelioThemeProvider, useDreelioThemeContext } from '../components/marketing/DreelioThemeContext'
import ResourcesSection from '../components/marketing/ResourcesSection'
import { Reveal } from '../components/marketing/reveal'
import { useRevealEngine } from '../components/marketing/reveal'
import TransitionLink from '../components/marketing/TransitionLink'

function MarketingResourcesContent() {
  const navigate = useNavigate()
  const { isDark } = useDreelioThemeContext()
  useRevealEngine()

  useEffect(() => {
    const prev = document.body.style.backgroundColor
    document.body.style.backgroundColor = isDark ? '#12100c' : '#efe8db'
    return () => {
      document.body.style.backgroundColor = prev
    }
  }, [isDark])

  return (
    <div
      className={`dreelio-landing${isDark ? ' dreelio-dark' : ''}`}
      style={{
        minHeight: '100vh',
        background: 'var(--canvas)',
        color: 'var(--ink)',
        fontFamily: 'var(--font)',
        WebkitFontSmoothing: 'antialiased',
        transition: 'background-color .35s var(--ease), color .35s var(--ease)',
      }}
    >
      <DreelioNav onStart={() => viewTransitionNavigate(navigate, '/analyze')} activePath="resources" />
      <main className="marketing-page-enter">
        <header
          className="section"
          style={{ paddingTop: 148, paddingBottom: 0, textAlign: 'center' }}
        >
          <div className="wrap" style={{ maxWidth: 720, margin: '0 auto' }}>
            <Reveal as="h1" className="h-xl reveal-d1" style={{ color: 'var(--ink)', margin: '0 0 16px' }}>
              Guides for every stage of your appeal
            </Reveal>
            <Reveal as="p" className="lead reveal-d2" style={{ margin: '0 0 24px' }}>
              Plain-English articles on denials, deadlines, and Indiana-specific rights — so you know what to do before
              you upload a single document.
            </Reveal>
            <Reveal delay={120} as="div" style={{ display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
              <TransitionLink to="/" className="btn btn-ghost">
                <span className="ms" style={{ fontSize: 18, marginRight: 4 }}>arrow_back</span>
                Back to home
              </TransitionLink>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => viewTransitionNavigate(navigate, '/analyze')}
              >
                Start Free Analysis
                <span className="ms arrow" style={{ fontSize: 18 }}>arrow_forward</span>
              </button>
            </Reveal>
          </div>
        </header>
        <ResourcesSection showBrowseLink />
      </main>
      <DreelioFooter />
    </div>
  )
}

export default function MarketingResourcesPage() {
  return (
    <DreelioThemeProvider>
      <MarketingResourcesContent />
    </DreelioThemeProvider>
  )
}
