import TransitionLink from './TransitionLink'

export default function DreelioFooter() {
  const cols = [
    {
      h: 'Product',
      links: [
        { label: 'How it works', href: '/#pipeline' },
        { label: 'Features', href: '/#features' },
        { label: 'Trust & Security', href: '/#trust' },
        { label: 'Start Analysis', href: '/analyze' },
      ],
    },
    {
      h: 'Resources',
      links: [
        { label: 'Guides & articles', href: '/resources' },
        { label: 'Indiana hub', href: '/indiana-resources' },
        { label: 'Plan types', href: '/indiana-resources' },
        { label: 'Code lookup', href: '/code-lookup' },
      ],
    },
    {
      h: 'Information',
      links: [
        { label: 'Contact', href: '#' },
        { label: 'Privacy', href: '#' },
        { label: 'Terms of use', href: '#' },
        { label: 'Accessibility', href: '#' },
      ],
    },
  ]

  return (
    <footer style={{ background: 'var(--dark)', color: 'var(--dark-ink)', paddingTop: 72 }}>
      <div className="wrap-wide">
        <div
          className="footer-grid"
          style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr 1fr 1fr', gap: 40, paddingBottom: 48 }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 16 }}>
              <span
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 8,
                  background: '#fff',
                  color: 'var(--accent)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  fontSize: 17,
                  letterSpacing: '-0.06em',
                }}
              >
                R
              </span>
              <span style={{ fontWeight: 800, fontSize: 22, letterSpacing: '-0.045em', color: '#fff' }}>Resolvly</span>
            </div>
            <p style={{ fontSize: 14.5, color: 'var(--dark-ink-2)', lineHeight: 1.6, maxWidth: 320, margin: 0 }}>
              AI-powered insurance claim &amp; billing debugger. Helping Hoosiers navigate denial complexity since 2026.
            </p>
          </div>
          {cols.map((c) => (
            <div key={c.h}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--dark-ink-2)',
                  marginBottom: 16,
                }}
              >
                {c.h}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                {c.links.map((l) =>
                  l.href === '#' ? (
                    <a
                      key={l.label}
                      href={l.href}
                      style={{
                        fontSize: 14.5,
                        color: 'var(--dark-ink)',
                        textDecoration: 'none',
                        opacity: 0.85,
                        transition: 'opacity .2s',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                      onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.85')}
                    >
                      {l.label}
                    </a>
                  ) : (
                    <TransitionLink
                      key={l.label}
                      to={l.href}
                      style={{
                        fontSize: 14.5,
                        color: 'var(--dark-ink)',
                        textDecoration: 'none',
                        opacity: 0.85,
                        transition: 'opacity .2s',
                      }}
                      onClick={(e) => {
                        e.currentTarget.style.opacity = '1'
                      }}
                    >
                      {l.label}
                    </TransitionLink>
                  ),
                )}
              </div>
            </div>
          ))}
        </div>
        <div
          style={{
            borderTop: '1px solid rgba(255,255,255,0.1)',
            padding: '24px 0 36px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 16,
          }}
        >
          <p style={{ fontSize: 12, color: 'var(--dark-ink-2)', margin: 0, maxWidth: 720, lineHeight: 1.6 }}>
            <strong style={{ color: 'var(--dark-ink)' }}>Not legal advice.</strong> Resolvly is an advocacy software
            platform and does not constitute a law firm or medical provider. We do not provide legal advice; all outputs
            are informational drafts requiring professional review.
          </p>
          <span style={{ fontSize: 12.5, color: 'var(--dark-ink-2)' }}>© 2026 Resolvly</span>
        </div>
      </div>
    </footer>
  )
}
