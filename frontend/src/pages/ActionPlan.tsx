import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { loadAnalysisBundle } from '../lib/sessionKeys'
import { postActionChecklist, postDeadlines, postExportIcs } from '../lib/api'

type StepRow = {
  num: number
  title: string
  desc: string
  why?: string
  active: boolean
  tag?: string
  tagClass?: string
}

const DEFAULT_STEPS: StepRow[] = [
  {
    num: 1,
    title: 'Acquire Medical Records & EOB',
    tag: 'Critical',
    tagClass: 'bg-primary-fixed text-on-primary-fixed',
    desc: 'You need the specific clinical notes from the July 14th session to counter the \'Medically Unnecessary\' denial.',
    why: 'Under Indiana Administrative Code 760 IAC 1-59, the insurer must provide a clinical rationale. Without your records, we cannot map your symptoms to their criteria.',
    active: true,
  },
  {
    num: 2,
    title: 'Draft Level-1 Clinical Appeal',
    desc: 'Utilize the \'Resolvly Drafting Room\' to generate a legal brief focused on medical necessity.',
    why: 'Level-1 is your contractual right to an internal review by a physician of the same specialty.',
    active: false,
  },
  {
    num: 3,
    title: 'Indiana External Review Request',
    desc: 'Submit the IDOI External Review Form if the Level-1 appeal is upheld.',
    active: false,
  },
  {
    num: 4,
    title: 'Final Settlement Negotiation',
    desc: 'Engagement of legal counsel for final dispute resolution on the outstanding $11,250 balance.',
    active: false,
  },
]

function fmtMoney(n: number | undefined | null) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function parsePart(iso: string | undefined) {
  if (!iso) return { m: '—', d: '—' }
  const d = new Date(iso + (iso.length === 10 ? 'T12:00:00' : ''))
  if (Number.isNaN(d.getTime())) return { m: '—', d: '—' }
  return { m: d.toLocaleString('en-US', { month: 'short' }), d: String(d.getDate()) }
}

function severityLabel(t: string | undefined) {
  if (t === 'urgent') return 'Urgent'
  if (t === 'routine') return 'Routine'
  return 'Time-Sensitive'
}

export default function ActionPlan() {
  const navigate = useNavigate()
  const [openStep, setOpenStep] = useState<number | null>(null)
  const [reminders, setReminders] = useState({ weekly: true, urgent: true, regulatory: false })
  const [steps, setSteps] = useState<StepRow[]>(DEFAULT_STEPS)
  const [deadlineInfo, setDeadlineInfo] = useState<Array<{ type: string; date?: string; ics_data?: string; source_law?: string }>>([])

  const bundle = useMemo(() => loadAnalysisBundle(), [])

  const ident = (bundle?.claim_object?.identification ?? {}) as Record<string, unknown>
  const financial = (bundle?.claim_object?.financial ?? {}) as Record<string, unknown>
  const denial = (bundle?.claim_object?.denial_reason ?? {}) as Record<string, unknown>
  const analysis = bundle?.analysis ?? {}
  const planCtx = bundle?.plan_context ?? {}
  const approval = (analysis.approval_probability ?? {}) as Record<string, unknown>
  const deadlinesAnalysis = (analysis.deadlines ?? {}) as Record<string, unknown>

  const caseRef = (ident.claim_reference_number as string) || 'Case #ID-440291'
  const billed = financial.billed_amount as number | undefined
  const paid = financial.insurer_paid_amount as number | undefined
  const denied = financial.denied_amount as number | undefined
  const prob = typeof approval.score === 'number' ? Math.round(approval.score * 100) : 84
  const isErisa = planCtx.regulation_type === 'erisa'

  const internal = deadlinesAnalysis.internal_appeal as Record<string, unknown> | undefined
  const external = deadlinesAnalysis.external_review as Record<string, unknown> | undefined
  const internalDate = internal?.date as string | undefined
  const externalDate = external?.date as string | undefined
  const intPart = parsePart(internalDate)
  const extPart = parsePart(externalDate)

  useEffect(() => {
    if (!bundle) return
    postActionChecklist(bundle.claim_object, bundle.analysis, bundle.enrichment)
      .then(res => {
        const raw = res.steps ?? []
        if (!raw.length) {
          setSteps(DEFAULT_STEPS)
          return
        }
        const mapped: StepRow[] = raw.map((s, i) => ({
          num: Number(s.number ?? i + 1),
          title: String(s.action ?? ''),
          ...(i === 0 ? { tag: 'Critical', tagClass: 'bg-primary-fixed text-on-primary-fixed' } : {}),
          desc: String(s.detail ?? ''),
          why: String(s.why ?? ''),
          active: i === 0,
        }))
        setSteps(mapped)
      })
      .catch(() => setSteps(DEFAULT_STEPS))

    postDeadlines(bundle.claim_object, bundle.analysis)
      .then(r => setDeadlineInfo(r.deadlines ?? []))
      .catch(() => setDeadlineInfo([]))
  }, [bundle])

  async function downloadIcs(which: 'internal' | 'external') {
    const row =
      which === 'internal'
        ? deadlineInfo.find(d => d.type === 'internal_appeal')
        : deadlineInfo.find(d => d.type === 'external_review')
    const date =
      which === 'internal' ? internalDate : externalDate
    if (row?.ics_data) {
      const blob = new Blob([row.ics_data], { type: 'text/calendar' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `deadline-${which}.ics`
      a.click()
      URL.revokeObjectURL(a.href)
      return
    }
    if (!date) return
    try {
      const blob = await postExportIcs({
        event_title: which === 'internal' ? 'Internal appeal deadline' : 'External review deadline',
        event_date: date.slice(0, 10),
        description: String(row?.source_law ?? ''),
        reminder_days_before: [30, 7],
      })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `deadline-${which}.ics`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch {
      /* keep UI unchanged on failure */
    }
  }

  const carcHint = Array.isArray(denial.carc_codes) && denial.carc_codes.length
    ? String(denial.carc_codes[0])
    : 'CO-197'

  return (
    <div className="bg-background text-on-surface antialiased min-h-screen flex flex-col">
      <Navbar />

      <main className="pt-24 pb-12 px-8 max-w-7xl mx-auto flex-grow">
        {/* Header */}
        <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-tertiary-fixed text-on-tertiary-fixed text-[10px] uppercase tracking-widest font-bold">
              <span className="material-symbols-outlined text-sm">priority_high</span>
              {severityLabel(analysis.severity_triage as string | undefined)}
            </div>
            <h1 className="text-5xl font-extrabold font-headline tracking-tighter text-primary">Action Plan &amp; Deadlines</h1>
            <p className="text-on-surface-variant max-w-2xl leading-relaxed">
              Your comprehensive recovery roadmap for {caseRef}. We have identified specific regulatory paths based on Indiana state law and ERISA guidelines.
            </p>
          </div>
          <div className="glass-card p-6 rounded-xl border border-outline-variant/15 flex items-center gap-6">
            <div className="relative w-20 h-20">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <path className="text-surface-container-high" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray="100, 100" strokeWidth="3" />
                <path className="text-primary" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray={`${prob}, 100`} strokeLinecap="round" strokeWidth="3" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center font-headline font-bold text-primary">{prob}%</div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-tighter text-on-surface-variant">Likelihood of Success</div>
              <div className="text-xl font-bold text-primary">Strong Appeal Case</div>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left: Strategy */}
          <div className="lg:col-span-8 space-y-8">
            {/* Financial Analysis */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/15 shadow-sm">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="font-headline font-bold text-lg">Bill Breakdown</h3>
                  <span className="material-symbols-outlined text-outline">account_balance_wallet</span>
                </div>
                <div className="space-y-4">
                  {[
                    { label: 'Billed Amount', value: fmtMoney(billed) === '—' ? '$4,435.00' : fmtMoney(billed), cls: '' },
                    { label: 'Plan Paid', value: fmtMoney(paid) === '—' ? '$96.00' : fmtMoney(paid), cls: 'text-emerald-700' },
                    { label: 'Denied (Disputed)', value: fmtMoney(denied) === '—' ? '$4,250.00' : fmtMoney(denied), cls: 'text-error' },
                  ].map(({ label, value, cls }) => (
                    <div key={label} className="flex justify-between items-center py-2 border-b border-surface-container">
                      <span className="text-on-surface-variant text-sm">{label}</span>
                      <span className={`font-headline font-bold ${cls}`}>{value}</span>
                    </div>
                  ))}
                  <div className="flex justify-between items-center pt-4">
                    <span className="text-primary font-bold">Disputed Gap</span>
                    <span className="text-2xl font-extrabold text-primary">{fmtMoney(denied) === '—' ? '$4,250.00' : fmtMoney(denied)}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/bill-breakdown')}
                  className="mt-5 w-full flex items-center justify-center gap-2 py-2.5 border border-primary text-primary text-xs font-bold rounded-lg hover:bg-primary hover:text-white transition-all"
                >
                  <span className="material-symbols-outlined text-sm">receipt_long</span>
                  View Full Bill Breakdown
                </button>
              </div>

              <div className="bg-secondary-container p-8 rounded-xl border border-outline-variant/15 relative overflow-hidden">
                <div className="relative z-10">
                  <h3 className="font-headline font-bold text-lg text-on-secondary-fixed-variant mb-4">Regulatory Routing</h3>
                  <div className="space-y-4">
                    <div className={`bg-white/50 p-4 rounded-lg ${isErisa ? 'opacity-40 grayscale' : ''}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="material-symbols-outlined text-sm">gavel</span>
                        <span className="text-xs font-bold uppercase tracking-widest text-on-secondary-fixed">Entity Determination</span>
                      </div>
                      <div className="text-xl font-extrabold text-on-secondary-fixed mb-1">IDOI (Indiana)</div>
                      <p className="text-sm text-on-secondary-fixed-variant leading-tight">This plan is fully insured and subject to IDOI IC 27-8-28 oversight.</p>
                    </div>
                    <div className={`${isErisa ? '' : 'opacity-40 grayscale pointer-events-none'}`}>
                      <div className="text-xs font-bold uppercase tracking-widest text-on-secondary-fixed">Alternative: ERISA</div>
                      <div className="text-lg font-bold">US Dept of Labor</div>
                    </div>
                  </div>
                </div>
                <span className="material-symbols-outlined absolute -right-8 -bottom-8 text-9xl text-on-secondary-container/10">policy</span>
              </div>
            </section>

            {/* Recovery Roadmap */}
            <section className="bg-surface-container-low p-8 rounded-xl">
              <h3 className="font-headline font-bold text-2xl text-primary mb-8">Recovery Roadmap</h3>
              <div className="relative">
                <div className="absolute top-8 left-4 bottom-8 w-0.5 bg-outline-variant/30"></div>
                <div className="space-y-10">
                  {steps.map(({ num, title, tag, tagClass, desc, why, active }) => (
                    <div key={num} className="relative pl-12">
                      <div className={`absolute left-0 top-0 w-8 h-8 rounded-full flex items-center justify-center font-bold z-10 shadow-lg ${active ? 'signature-cta text-on-primary' : 'bg-surface-container-highest border-2 border-outline-variant text-on-surface-variant'}`}>
                        {num}
                      </div>
                      <div className={`bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10 shadow-sm ${!active ? 'opacity-80' : ''}`}>
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-bold text-lg">{title}</h4>
                          {tag && <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${tagClass}`}>{tag}</span>}
                        </div>
                        <p className="text-on-surface-variant text-sm mb-4">{desc}</p>
                        {why && (
                          <details className="text-sm" open={openStep === num} onToggle={() => setOpenStep(openStep === num ? null : num)}>
                            <summary className="cursor-pointer text-primary font-semibold flex items-center gap-1 hover:underline">
                              Why is this required?
                            </summary>
                            <div className="mt-3 p-4 bg-surface-container rounded-lg text-on-surface-variant italic">{why}</div>
                          </details>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>

          {/* Right: Deadlines & Actions */}
          <aside className="lg:col-span-4 space-y-8">
            {/* Deadlines */}
            <div className="bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/15 shadow-sm">
              <h3 className="font-headline font-bold text-xl mb-6">Critical Deadlines</h3>
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-12 h-14 bg-error-container rounded-lg flex flex-col items-center justify-center">
                    <span className="text-[10px] font-bold text-on-error-container uppercase">{intPart.m}</span>
                    <span className="text-xl font-extrabold text-on-error-container leading-none">{intPart.d}</span>
                  </div>
                  <div className="flex-grow">
                    <div className="text-sm font-bold text-primary">Internal Appeal Window</div>
                    <div className="text-xs text-on-surface-variant">{internal?.source ? String(internal.source) : '180 days from EOB receipt'}</div>
                    <button
                      type="button"
                      onClick={() => void downloadIcs('internal')}
                      className="mt-2 text-primary text-[10px] font-bold uppercase tracking-widest flex items-center gap-1 hover:text-primary-container"
                    >
                      <span className="material-symbols-outlined text-sm">calendar_add_on</span> Add to Calendar
                    </button>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-12 h-14 bg-surface-container rounded-lg flex flex-col items-center justify-center opacity-60">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase">{extPart.m}</span>
                    <span className="text-xl font-extrabold text-on-surface-variant leading-none">{extPart.d}</span>
                  </div>
                  <div className="flex-grow">
                    <div className="text-sm font-bold text-on-surface-variant">IDOI Filing Deadline</div>
                    <div className="text-xs text-on-surface-variant">External Review window</div>
                    <button
                      type="button"
                      onClick={() => void downloadIcs('external')}
                      className="mt-2 text-primary text-[10px] font-bold uppercase tracking-widest flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-sm">calendar_today</span> .ics Export
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Reminders */}
            <div className="bg-primary p-8 rounded-xl text-on-primary">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined">mail</span>
                <h3 className="font-headline font-bold text-lg">Reminders</h3>
              </div>
              <p className="text-on-primary-container text-sm mb-6">Stay ahead of deadlines. We will notify you 7 days before any critical window closes.</p>
              <div className="space-y-3">
                {[
                  { key: 'weekly', label: 'Weekly Case Summary' },
                  { key: 'urgent', label: 'Urgent Deadline Alerts' },
                  { key: 'regulatory', label: 'Regulatory Policy Updates' },
                ].map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-3 cursor-pointer group">
                    <input
                      checked={reminders[key as keyof typeof reminders]}
                      onChange={() => setReminders(r => ({ ...r, [key]: !r[key as keyof typeof reminders] }))}
                      className="rounded bg-primary-container border-none focus:ring-0"
                      type="checkbox"
                    />
                    <span className="text-sm font-medium group-hover:text-primary-container transition-colors">{label}</span>
                  </label>
                ))}
              </div>
              <button className="w-full mt-6 py-3 bg-white text-primary font-bold rounded-lg text-sm shadow-xl hover:bg-surface-container transition-colors">
                Update Preferences
              </button>
            </div>

            {/* Case Manager */}
            <div className="bg-surface-container-high p-6 rounded-xl border border-outline-variant/15">
              <div className="flex items-center gap-4 mb-4">
                <img
                  alt="Sarah Miller JD"
                  className="w-12 h-12 rounded-full object-cover"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuCGOAQm1iFuZ2KbPjuv9fhHlSGm2e3Qpc2aVq_OuCy8M3KN-zBb5FaqKOdaI-1_xRbVKp2WA1xFTAEBQVYOKgNSS3Xgy7NcRGws6VyMWuEMW7iLTPWIgVXUfq4jIj9GkHAehtXnL_pRVTWFqCfRHJ3JeOaUEE5S-XETtqYPAM9nPMY7E4DUKn8HwsYwfFyk-AmPhl2n0g1eCk3IbyxK9d4FryzyCXEJ_XWIubsxYh6A7okr3EBik8Uwgmq1RGqIkf8EPkaEnZPXyX0"
                />
                <div>
                  <div className="text-sm font-bold text-primary">Sarah Miller, JD</div>
                  <div className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">Indiana Advocacy Lead</div>
                </div>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed mb-4">
                &quot;Based on your denial code ({carcHint}), I recommend prioritizing the medical record collection immediately.&quot;
              </p>
              <button className="w-full py-2 border border-primary text-primary text-xs font-bold rounded uppercase tracking-widest hover:bg-primary hover:text-white transition-all">
                Chat with Sarah
              </button>
            </div>
          </aside>
        </div>
      </main>

      <Footer disclaimer="Resolvly is not a law firm. Information provided does not constitute legal advice. Action plans are based on algorithmic analysis of insurance denial patterns and Indiana Department of Insurance (IDOI) public records." />
    </div>
  )
}
