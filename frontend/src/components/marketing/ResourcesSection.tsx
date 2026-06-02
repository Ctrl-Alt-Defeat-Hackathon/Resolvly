import { Reveal } from './reveal'
import TransitionLink from './TransitionLink'

function Thumb({ icon, tint }: { icon: string; tint: string }) {
  return (
    <div
      style={{
        position: 'relative',
        height: 168,
        borderRadius: 'var(--r-md)',
        overflow: 'hidden',
        background: tint,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.5 }}>
        <defs>
          <pattern id={'st' + icon} width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="14" fill="rgba(0,52,97,0.06)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#st${icon})`} />
      </svg>
      <span className="ms" style={{ fontSize: 44, color: 'var(--accent)', opacity: 0.55, position: 'relative' }}>
        {icon}
      </span>
    </div>
  )
}

export default function ResourcesSection({ showBrowseLink = true }: { showBrowseLink?: boolean }) {
  const posts = [
    { tag: 'Plan Types', t: 'Self-funded or fully insured? Why it decides your whole appeal', icon: 'account_tree', tint: '#e6eef4', href: 'https://triagecancer.org/understanding-health-insurance-whats-the-difference-between-self-insured-and-insured-employer-plans' },
    { tag: 'Deadlines', t: 'The 180-day clock: Indiana appeal windows explained', icon: 'event', tint: '#f4eede', href: 'https://www.in.gov/idoi/consumer-services/internal-and-external-grievance-procedures/' },
    { tag: 'Basics', t: 'Reading your EOB without the headache', icon: 'receipt_long', tint: '#e7f1ec', href: 'https://www.cms.gov/medical-bill-rights/help/guides/explanation-of-benefits' },
  ]

  return (
    <section id="resources" className="section marketing-page-enter">
      <div className="wrap-wide">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            flexWrap: 'wrap',
            gap: 20,
            marginBottom: 48,
          }}
        >
          <div>
            <Reveal as="h2" className="h-xl reveal-d1" style={{ color: 'var(--ink)', margin: 0 }}>
              Know your rights, in plain English
            </Reveal>
          </div>
          {showBrowseLink && (
            <Reveal delay={120} as="div" style={{ alignSelf: 'flex-end' }}>
              <TransitionLink to="/indiana-resources" className="btn btn-ghost">
                Browse all resources <span className="ms arrow" style={{ fontSize: 18 }}>arrow_forward</span>
              </TransitionLink>
            </Reveal>
          )}
        </div>

        <div className="resources-grid" style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 24 }}>
          <Reveal as="a" href="https://etactics.com/blog/denial-code-co-197" target="_blank" rel="noopener noreferrer" className="card card-hover" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', textDecoration: 'none', color: 'inherit' }}>
            <div
              style={{
                position: 'relative',
                height: 300,
                background: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
              }}
            >
              <span className="ms" style={{ fontSize: 150, color: 'rgba(255,255,255,0.10)', position: 'absolute' }}>
                policy
              </span>
              <span className="chip" style={{ position: 'absolute', top: 18, left: 18, background: '#fff' }}>
                Must Read
              </span>
              <div style={{ position: 'relative', color: '#fff', textAlign: 'center', padding: 24 }}>
                <span
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 14,
                    fontWeight: 700,
                    background: 'rgba(255,255,255,0.14)',
                    padding: '6px 14px',
                    borderRadius: 8,
                  }}
                >
                  CO-197
                </span>
              </div>
            </div>
            <div style={{ padding: 32 }}>
              <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.02em' }}>
                Appeals · 6 min read
              </span>
              <h3 className="h-lg" style={{ color: 'var(--ink)', margin: '10px 0 12px' }}>
                What CO-197 really means — and how to reverse it
              </h3>
              <p className="body" style={{ margin: 0, maxWidth: 480 }}>
                A prior-authorization denial isn&apos;t a verdict on your care. Here&apos;s the procedural fix that resolves
                most CO-197s before they ever reach external review.
              </p>
            </div>
          </Reveal>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {posts.map((p, i) => (
              <Reveal
                key={p.t}
                as="a"
                href={p.href}
                target="_blank"
                rel="noopener noreferrer"
                delay={i * 90}
                className="card card-hover"
                style={{ padding: 16, display: 'flex', gap: 16, alignItems: 'center', textDecoration: 'none', color: 'inherit' }}
              >
                <div style={{ width: 96, flex: 'none' }}>
                  <Thumb icon={p.icon} tint={p.tint} />
                </div>
                <div>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>{p.tag}</span>
                  <h4
                    style={{
                      fontSize: 17,
                      fontWeight: 700,
                      color: 'var(--ink)',
                      margin: '6px 0 0',
                      letterSpacing: '-0.02em',
                      lineHeight: 1.25,
                    }}
                  >
                    {p.t}
                  </h4>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
