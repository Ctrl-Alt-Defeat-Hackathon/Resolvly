import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { analysisBundleFingerprint, loadAnalysisBundle } from '../lib/sessionKeys'
import { postExportIcs } from '../lib/api'
import {
  getCachedActionChecklist,
  getCachedAppealLetter,
  getCachedCompleteness,
  getCachedDeadlines,
  getCachedProviderBrief,
  getCachedRoutingCard,
  getCachedSummary,
  getCachedAssumptions,
} from '../lib/outputsCache'

type StepRow = {
  num: number
  title: string
  desc: string
  why?: string
  active: boolean
  tag?: string
  tagClass?: string
}

/** Shown only if the output agent could not return steps */
const FALLBACK_STEPS: StepRow[] = [
  {
    num: 1,
    title: 'Review your uploaded denial materials',
    desc: 'Action steps could not be loaded from the server (network error or the request failed). Confirm you finished analysis on /analyze and try refreshing. If it persists, check that the backend is running and reachable.',
    active: true,
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

function buildPatientInfo(claim: Record<string, unknown>): Record<string, string> {
  const pp = (claim.patient_provider ?? {}) as Record<string, unknown>
  const ar = (claim.appeal_rights ?? {}) as Record<string, unknown>
  const out: Record<string, string> = {}
  const name = typeof pp.patient_full_name === 'string' ? pp.patient_full_name.trim() : ''
  if (name) out.name = name
  const addr = typeof pp.facility_address === 'string' ? pp.facility_address.trim() : ''
  if (addr) out.address = addr
  const phone = typeof ar.insurer_appeals_phone === 'string' ? ar.insurer_appeals_phone.trim() : ''
  if (phone) out.phone = phone
  return out
}

function RoutingRouteBlock({
  route,
  muted,
  pathLabel,
  fillHeight,
}: {
  route: Record<string, unknown>
  muted?: boolean
  pathLabel: string
  /** When true, stretch to fill parent flex height (sidebar regulatory card) */
  fillHeight?: boolean
}) {
  const contact = (route.contact ?? {}) as Record<string, string>
  const steps = Array.isArray(route.process_steps) ? (route.process_steps as string[]) : []
  const rootFlex = fillHeight ? 'flex min-h-0 h-full flex-col' : ''
  return (
    <div
      className={`rounded-lg bg-white/50 p-4 dark:bg-slate-950/90 dark:ring-1 dark:ring-slate-600/50 ${
        muted ? 'opacity-40 grayscale' : ''
      } ${rootFlex}`}
    >
      <div className="shrink-0 mb-1 flex items-center gap-2">
        <span className="material-symbols-outlined text-sm text-on-secondary-fixed dark:text-slate-300">gavel</span>
        <span className="text-xs font-bold uppercase tracking-widest text-on-secondary-fixed dark:text-slate-300">
          {pathLabel}
        </span>
      </div>
      <div className="shrink-0 mb-1 text-lg font-extrabold text-on-secondary-fixed dark:text-white">
        {String(route.route_name ?? '—')}
      </div>
      <p className="shrink-0 text-xs leading-snug text-on-secondary-fixed-variant dark:text-slate-400 mb-3">
        {String(route.legal_basis ?? '')}
      </p>
      {(contact.name || contact.phone || contact.website || contact.complaint_url) && (
        <div className="shrink-0 text-xs space-y-1 text-on-secondary-fixed-variant dark:text-slate-400 mb-3">
          {contact.name ? <p className="font-semibold text-on-secondary-fixed dark:text-slate-200">{contact.name}</p> : null}
          {contact.phone ? <p>Tel: {contact.phone}</p> : null}
          {contact.website ? (
            <a href={contact.website} target="_blank" rel="noopener noreferrer" className="text-primary underline break-all">
              {contact.website}
            </a>
          ) : null}
          {contact.complaint_url ? (
            <a href={contact.complaint_url} target="_blank" rel="noopener noreferrer" className="block text-primary underline">
              Complaints / EBSA
            </a>
          ) : null}
        </div>
      )}
      {steps.length > 0 ? (
        <ol
          className={`list-decimal list-inside text-xs text-on-secondary-fixed-variant dark:text-slate-400 space-y-1 ${
            fillHeight ? 'min-h-0 flex-1 overflow-y-auto py-1' : 'mb-2'
          }`}
        >
          {steps.slice(0, 6).map(s => (
            <li key={s.slice(0, 40)}>{s}</li>
          ))}
        </ol>
      ) : (
        fillHeight ? <div className="min-h-0 flex-1" aria-hidden /> : null
      )}
      {route.notes ? (
        <p className="shrink-0 text-[11px] italic text-on-secondary-fixed-variant dark:text-slate-500 pt-2">
          {String(route.notes)}
        </p>
      ) : null}
    </div>
  )
}

export default function ActionPlan() {
  const navigate = useNavigate()
  const [openStep, setOpenStep] = useState<number | null>(null)
  const [steps, setSteps] = useState<StepRow[]>([])
  const [deadlineInfo, setDeadlineInfo] = useState<Array<{ type: string; date?: string; ics_data?: string; source_law?: string }>>([])
  const [summaryState, setSummaryState] = useState<{
    loading: boolean
    error: string | null
    summary_text: string
    reading_level: string
    key_points: string[]
  }>({
    loading: true,
    error: null,
    summary_text: '',
    reading_level: '',
    key_points: [],
  })

  const [routingState, setRoutingState] = useState<{
    loading: boolean
    error: string | null
    data: Record<string, unknown> | null
  }>({ loading: false, error: null, data: null })

  type CompletenessData = {
    score: number
    score_percentage: string
    regulation_standard: string
    deficient: boolean
    escalation_available: boolean
    escalation_reason: string
    checklist: Array<{
      field: string
      present: boolean
      required_by: string
      why_it_matters: string
      action_if_missing: string
    }>
    present_count: number
    missing_count: number
    summary: string
  }

  const [completenessState, setCompletenessState] = useState<{
    loading: boolean
    error: string | null
    data: CompletenessData | null
  }>({ loading: false, error: null, data: null })

  const [providerBriefState, setProviderBriefState] = useState<{
    loading: boolean
    error: string | null
    brief_text: string
  }>({ loading: false, error: null, brief_text: '' })

  const bundleFingerprint = analysisBundleFingerprint()
  const bundle = useMemo(() => loadAnalysisBundle(), [bundleFingerprint])

  const financial = (bundle?.claim_object?.financial ?? {}) as Record<string, unknown>
  const analysis = bundle?.analysis ?? {}
  const planCtx = bundle?.plan_context ?? {}
  const enrichment = (bundle?.enrichment ?? {}) as Record<string, unknown>
  const stateRules = (enrichment.state_rules ?? {}) as Record<string, unknown>
  const approval = (analysis.approval_probability ?? {}) as Record<string, unknown>
  const deadlinesAnalysis = (analysis.deadlines ?? {}) as Record<string, unknown>
  const rootCause = (analysis.root_cause ?? {}) as Record<string, unknown>

  const billed = financial.billed_amount as number | undefined
  const paid = financial.insurer_paid_amount as number | undefined
  const denied = financial.denied_amount as number | undefined
  const prob = typeof approval.score === 'number' ? Math.round(approval.score * 100) : null
  const routingKey = stateRules.regulatory_routing as string | undefined
  const isErisaEnrichment =
    routingKey === 'erisa_federal' ||
    (!routingKey && String(planCtx.regulation_type || '') === 'erisa')
  const routingNarrative =
    (typeof stateRules.routing_reason === 'string' && stateRules.routing_reason) ||
    (isErisaEnrichment
      ? 'Self-funded employer plans generally follow ERISA; state DOI typically does not regulate the plan.'
      : 'State-regulated plans generally follow ACA appeals rules and your state Department of Insurance.')
  const doiContact = (stateRules.doi_contact ?? {}) as Record<string, string>

  const internal = deadlinesAnalysis.internal_appeal as Record<string, unknown> | undefined
  const external = deadlinesAnalysis.external_review as Record<string, unknown> | undefined
  const internalDate = internal?.date as string | undefined
  const externalDate = external?.date as string | undefined
  const intPart = parsePart(internalDate)
  const extPart = parsePart(externalDate)

  useEffect(() => {
    if (!bundle) {
      setSummaryState({
        loading: false,
        error: 'No saved analysis. Complete a run on /analyze first.',
        summary_text: '',
        reading_level: '',
        key_points: [],
      })
      setRoutingState({ loading: false, error: null, data: null })
      setCompletenessState({ loading: false, error: null, data: null })
      setProviderBriefState({ loading: false, error: null, brief_text: '' })
      setSteps([])
      setDeadlineInfo([])
      return
    }
    setRoutingState({ loading: true, error: null, data: null })
    setCompletenessState({ loading: true, error: null, data: null })
    setProviderBriefState({ loading: true, error: null, brief_text: '' })
    getCachedRoutingCard(bundle.claim_object, bundle.analysis, bundle.enrichment)
      .then(data => setRoutingState({ loading: false, error: null, data }))
      .catch(() =>
        setRoutingState({
          loading: false,
          error: 'Could not load regulatory routing card.',
          data: null,
        })
      )
    getCachedCompleteness(bundle.claim_object, bundle.analysis, bundle.enrichment)
      .then(data => setCompletenessState({ loading: false, error: null, data }))
      .catch(() =>
        setCompletenessState({
          loading: false,
          error: 'Could not load denial-letter completeness report.',
          data: null,
        })
      )

    getCachedProviderBrief(bundle.claim_object, bundle.analysis, bundle.enrichment)
      .then(res =>
        setProviderBriefState({
          loading: false,
          error: null,
          brief_text: String(res.brief_text ?? '').trim(),
        })
      )
      .catch(() =>
        setProviderBriefState({
          loading: false,
          error: 'Could not load provider brief. Ensure GROQ_API_KEY or GEMINI_API_KEY is set on the server.',
          brief_text: '',
        })
      )

    setSummaryState(s => ({ ...s, loading: true, error: null }))
    getCachedSummary(bundle.claim_object, bundle.analysis, bundle.enrichment)
      .then(res =>
        setSummaryState({
          loading: false,
          error: null,
          summary_text: res.summary_text ?? '',
          reading_level: res.reading_level ?? '',
          key_points: Array.isArray(res.key_points) ? res.key_points : [],
        })
      )
      .catch(() =>
        setSummaryState({
          loading: false,
          error: 'Could not load summary. Check that analysis completed and the server has GROQ_API_KEY or GEMINI_API_KEY set.',
          summary_text: '',
          reading_level: '',
          key_points: [],
        })
      )

    getCachedActionChecklist(bundle.claim_object, bundle.analysis, bundle.enrichment)
      .then(res => {
        const raw = res.steps ?? []
        if (!raw.length) {
          setSteps(FALLBACK_STEPS)
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
      .catch(() => setSteps(FALLBACK_STEPS))

    getCachedDeadlines(bundle.claim_object, bundle.analysis)
      .then(r => setDeadlineInfo(r.deadlines ?? []))
      .catch(() => setDeadlineInfo([]))

    // Prefetch appeal letter in background so AppealDrafting opens faster.
    // Do not block this page on the result.
    const patientInfo = buildPatientInfo(bundle.claim_object)
    void getCachedAppealLetter(bundle.claim_object, bundle.analysis, bundle.enrichment, patientInfo)

    // Prefetch assumptions panel in background so the sidebar loads instantly.
    void getCachedAssumptions(bundle.claim_object, bundle.analysis, bundle.enrichment)
  }, [bundle, bundleFingerprint])

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

  return (
    <div className="bg-background text-on-background selection:bg-secondary-container antialiased min-h-screen flex flex-col">
      <Navbar />

      <main className="pt-24 pb-12 flex-grow">
        <div className="editorial-margin">
        {/* Header */}
        <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-tertiary-fixed text-on-tertiary-fixed text-[10px] uppercase tracking-widest font-bold">
              <span className="material-symbols-outlined text-sm">priority_high</span>
              {severityLabel(analysis.severity_triage as string | undefined)}
            </div>
            <h1 className="text-5xl font-extrabold font-headline tracking-tighter text-primary">Action Plan &amp; Deadlines</h1>
          </div>
          <div className="glass-card p-6 rounded-xl border border-outline-variant/15 flex items-center gap-6">
            <div className="relative w-20 h-20">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <path className="text-surface-container-high" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray="100, 100" strokeWidth="3" />
                <path className="text-primary" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray={`${prob}, 100`} strokeLinecap="round" strokeWidth="3" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center font-headline font-bold text-primary">
                {prob != null ? `${prob}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-tighter text-on-surface-variant">Likelihood of Success</div>
              <div className="text-xl font-bold text-primary">
                {typeof rootCause.category === 'string'
                  ? rootCause.category.replace(/_/g, ' ')
                  : 'Analysis-based estimate'}
              </div>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:items-stretch">
          {/* Left: Strategy */}
          <div className="lg:col-span-8 space-y-8">
            {/* Denial summary — same grid width as bill + regulatory row (one spanned cell) */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4" aria-labelledby="denial-summary-heading">
              <div className="md:col-span-2 rounded-xl border border-outline-variant/15 bg-surface-container-lowest shadow-sm overflow-hidden flex flex-col md:min-h-[28rem]">
                <div className="flex flex-col md:flex-row md:items-stretch flex-1 min-h-0">
                  <div className="flex-1 p-8 md:border-r border-outline-variant/15 flex flex-col min-w-0">
                    <div className="flex items-center justify-between gap-4 mb-4">
                      <h2 id="denial-summary-heading" className="font-headline font-bold text-xl text-primary">
                        Denial summary
                      </h2>
                      {summaryState.reading_level ? (
                        <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant shrink-0">
                          Reading level: {summaryState.reading_level}
                        </span>
                      ) : null}
                    </div>
                    {summaryState.loading && (
                      <div className="space-y-3 flex-1">
                        <div className="h-4 bg-surface-container-high rounded animate-pulse w-full" />
                        <div className="h-4 bg-surface-container-high rounded animate-pulse w-[92%]" />
                        <div className="h-4 bg-surface-container-high rounded animate-pulse w-4/5" />
                      </div>
                    )}
                    {!summaryState.loading && summaryState.error && (
                      <p className="text-sm text-on-surface-variant flex-1">{summaryState.error}</p>
                    )}
                    {!summaryState.loading && !summaryState.error && summaryState.summary_text && (
                      <div className="text-on-surface text-sm leading-relaxed whitespace-pre-wrap flex-1">{summaryState.summary_text}</div>
                    )}
                    {!summaryState.loading && !summaryState.error && !summaryState.summary_text && (
                      <p className="text-sm text-on-surface-variant flex-1">No summary text returned.</p>
                    )}
                  </div>
                  <div className="w-full md:w-[min(100%,22rem)] lg:w-80 shrink-0 p-8 bg-surface-container/40 dark:bg-surface-container-high/30 flex flex-col border-t md:border-t-0 border-outline-variant/15">
                    <h3 className="font-headline font-bold text-sm uppercase tracking-widest text-on-surface-variant mb-4">
                      Key points
                    </h3>
                    {summaryState.loading && (
                      <ul className="space-y-3 flex-1">
                        {[1, 2, 3].map(i => (
                          <li key={i} className="h-3 bg-surface-container-high rounded animate-pulse" />
                        ))}
                      </ul>
                    )}
                    {!summaryState.loading && summaryState.key_points.length > 0 && (
                      <ul className="space-y-3 list-disc list-inside text-sm text-on-surface marker:text-primary flex-1">
                        {summaryState.key_points.map((pt, i) => (
                          <li key={i}>{pt}</li>
                        ))}
                      </ul>
                    )}
                    {!summaryState.loading && !summaryState.key_points.length && (
                      <p className="text-xs text-on-surface-variant flex-1">
                        {summaryState.error ? '—' : 'Key takeaways will appear here when the summary loads.'}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </section>

            {/* Recovery Roadmap — before bill breakdown & regulatory routing */}
            <section className="bg-surface-container-low p-8 rounded-xl border border-outline-variant/15 shadow-sm">
              <h3 className="font-headline font-bold text-2xl text-primary mb-6">Recovery Roadmap</h3>
              <div className="relative">
                <div className="absolute top-8 left-4 bottom-8 w-0.5 bg-outline-variant/30"></div>
                <div className="space-y-10">
                  {bundle && steps.length === 0 && (
                    <p className="text-sm text-on-surface-variant">Loading action steps from your analysis…</p>
                  )}
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

            {/* Denial letter completeness — POST /outputs/completeness */}
            <section className="bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/15 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
                <div>
                  <h3 className="font-headline font-bold text-xl text-primary">Denial Notice Completeness</h3>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">
                    POST /outputs/completeness
                  </p>
                </div>
                {completenessState.data ? (
                  <div className="text-right">
                    <div className="text-3xl font-extrabold text-primary">{completenessState.data.score_percentage}</div>
                    <div className="text-[10px] text-on-surface-variant">{completenessState.data.regulation_standard}</div>
                  </div>
                ) : null}
              </div>
              {completenessState.loading && (
                <div className="space-y-3">
                  <div className="h-4 bg-surface-container-high rounded animate-pulse w-full" />
                  <div className="h-4 bg-surface-container-high rounded animate-pulse w-[94%]" />
                  <div className="h-24 bg-surface-container-high rounded animate-pulse w-full" />
                </div>
              )}
              {!completenessState.loading && completenessState.error && (
                <p className="text-sm text-error">{completenessState.error}</p>
              )}
              {!completenessState.loading && completenessState.data && (
                <>
                  <p className="text-sm text-on-surface-variant leading-relaxed mb-4">{completenessState.data.summary}</p>
                  {completenessState.data.escalation_available && completenessState.data.escalation_reason ? (
                    <p className="text-xs bg-tertiary-container/30 border border-tertiary/20 rounded-lg p-3 mb-4 text-on-surface">
                      {completenessState.data.escalation_reason}
                    </p>
                  ) : null}
                  <div className="rounded-lg border border-outline-variant/15 overflow-hidden flex flex-col max-h-[min(28rem,55vh)]">
                    <div className="overflow-x-auto overflow-y-auto overscroll-contain min-h-0 flex-1">
                      <table className="w-full text-sm min-w-[20rem]">
                        <thead className="sticky top-0 z-[1] bg-surface-container-high text-left text-[10px] uppercase tracking-widest text-on-surface-variant shadow-[0_1px_0_0_rgba(0,0,0,0.06)]">
                          <tr>
                            <th className="p-3 font-bold">Required element</th>
                            <th className="p-3 font-bold w-24">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {completenessState.data.checklist.map(row => (
                            <tr key={row.field} className="border-t border-outline-variant/10">
                              <td className="p-3 align-top">
                                <div className="font-semibold text-on-surface">{row.field}</div>
                                <div className="text-xs text-on-surface-variant mt-1">{row.why_it_matters}</div>
                                {!row.present ? (
                                  <div className="text-xs text-primary mt-2">
                                    <span className="font-bold">If missing:</span> {row.action_if_missing}
                                  </div>
                                ) : null}
                                <div className="text-[10px] text-on-surface-variant/80 mt-1 italic">{row.required_by}</div>
                              </td>
                              <td className="p-3 align-top">
                                <span
                                  className={`inline-block text-[10px] font-bold uppercase px-2 py-1 rounded ${
                                    row.present ? 'bg-emerald-100 text-emerald-900' : 'bg-error-container text-on-error-container'
                                  }`}
                                >
                                  {row.present ? 'Present' : 'Missing'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
              {!completenessState.loading && !completenessState.data && !completenessState.error && bundle && (
                <p className="text-sm text-on-surface-variant">No completeness data returned.</p>
              )}
            </section>
          </div>

          {/* Right: Deadlines & Actions — stretches to match main column height */}
          <aside className="lg:col-span-4 flex flex-col gap-8 lg:h-full lg:min-h-0">
            {/* Deadlines */}
            <div className="bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/15 shadow-sm shrink-0">
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
                    <div className="text-sm font-bold text-on-surface-variant">External review / IDOI</div>
                    <div className="text-xs text-on-surface-variant">
                      {external && typeof external.source === 'string' && external.source.trim()
                        ? external.source
                        : external && typeof (external as { note?: string }).note === 'string'
                          ? String((external as { note?: string }).note)
                          : 'External review window (see your state DOI or plan documents)'}
                    </div>
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

            {/* Provider brief — sidebar, below deadlines */}
            <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/15 shadow-sm shrink-0">
              <div className="flex items-start gap-2 mb-3">
                <span className="material-symbols-outlined text-primary text-xl shrink-0">stethoscope</span>
                <div>
                  <h3 className="font-headline font-bold text-lg text-primary leading-tight">Provider brief</h3>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">
                    For your treating physician
                  </p>
                </div>
              </div>
              {providerBriefState.loading && (
                <div className="space-y-2">
                  <div className="h-2.5 bg-surface-container-high rounded animate-pulse w-full" />
                  <div className="h-2.5 bg-surface-container-high rounded animate-pulse w-[92%]" />
                  <div className="h-24 bg-surface-container-high rounded animate-pulse w-full" />
                </div>
              )}
              {!providerBriefState.loading && providerBriefState.error && (
                <p className="text-xs text-error leading-snug">{providerBriefState.error}</p>
              )}
              {!providerBriefState.loading && !providerBriefState.error && providerBriefState.brief_text && (
                <div className="rounded-lg border border-outline-variant/20 bg-surface-container-lowest p-3 max-h-[min(20rem,42vh)] overflow-y-auto overscroll-contain">
                  <pre className="text-xs whitespace-pre-wrap font-sans text-on-surface leading-relaxed">
                    {providerBriefState.brief_text}
                  </pre>
                </div>
              )}
              {!providerBriefState.loading && !providerBriefState.error && !providerBriefState.brief_text && bundle && (
                <p className="text-xs text-on-surface-variant">No provider brief returned.</p>
              )}
            </div>

            {/* Bill + Regulatory: grow to fill remaining column height */}
            <div className="flex flex-col gap-8 flex-1 min-h-0">
            {/* Bill Breakdown — sidebar */}
            <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/15 shadow-sm shrink-0">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-headline font-bold text-base">Bill Breakdown</h3>
                <span className="material-symbols-outlined text-outline text-lg">account_balance_wallet</span>
              </div>
              <div className="space-y-3">
                {[
                  { label: 'Billed Amount', value: fmtMoney(billed), cls: '' },
                  { label: 'Plan Paid', value: fmtMoney(paid), cls: 'text-emerald-700' },
                  { label: 'Denied (Disputed)', value: fmtMoney(denied), cls: 'text-error' },
                ].map(({ label, value, cls }) => (
                  <div key={label} className="flex justify-between items-center py-1.5 border-b border-surface-container text-sm">
                    <span className="text-on-surface-variant">{label}</span>
                    <span className={`font-headline font-bold text-sm ${cls}`}>{value}</span>
                  </div>
                ))}
                <div className="flex justify-between items-center pt-2">
                  <span className="text-primary font-bold text-sm">Disputed Gap</span>
                  <span className="text-lg font-extrabold text-primary">{fmtMoney(denied)}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => navigate('/bill-breakdown')}
                className="mt-4 w-full flex items-center justify-center gap-2 py-2.5 border border-primary text-primary text-[11px] font-bold rounded-lg hover:bg-primary hover:text-white transition-all"
              >
                <span className="material-symbols-outlined text-sm">receipt_long</span>
                View Full Bill Breakdown
              </button>
            </div>

            {/* Regulatory Routing — grows with column; routes stacked tightly, scroll if needed */}
            <div className="relative overflow-hidden rounded-xl border border-outline-variant/15 bg-secondary-container p-6 dark:border-slate-600/40 dark:bg-slate-800/90 flex flex-col flex-1 min-h-0">
              <div className="relative z-10 flex min-h-0 flex-1 flex-col">
                <h3 className="mb-3 font-headline text-base font-bold text-on-secondary-fixed-variant dark:text-slate-200 shrink-0">
                  Regulatory Routing
                </h3>
                {routingState.loading && (
                  <div className="flex min-h-0 flex-1 flex-col justify-center gap-3 py-2">
                    <div className="h-3 bg-white/30 rounded animate-pulse w-full" />
                    <div className="h-16 bg-white/20 rounded animate-pulse w-full" />
                    <div className="h-12 bg-white/20 rounded animate-pulse w-[88%]" />
                  </div>
                )}
                {!routingState.loading && routingState.data && (
                  <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden rounded-lg border border-white/10 bg-white/5 p-3 dark:border-slate-600/40 dark:bg-slate-900/40">
                    {routingState.data.primary_route && typeof routingState.data.primary_route === 'object' ? (
                      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
                        <RoutingRouteBlock
                          pathLabel="Primary regulatory path"
                          route={routingState.data.primary_route as Record<string, unknown>}
                          muted={false}
                          fillHeight
                        />
                      </div>
                    ) : null}
                    {routingState.data.secondary_route && typeof routingState.data.secondary_route === 'object' ? (
                      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
                        <RoutingRouteBlock
                          pathLabel="Secondary / alternate path"
                          route={routingState.data.secondary_route as Record<string, unknown>}
                          muted={routingState.data.routing === 'erisa_federal'}
                          fillHeight
                        />
                      </div>
                    ) : null}
                  </div>
                )}
                {!routingState.loading && !routingState.data && (
                  <div className="flex min-h-0 flex-1 flex-col space-y-2 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-4 dark:border-slate-600/40 dark:bg-slate-900/40">
                    {routingState.error ? (
                      <p className="text-xs text-on-secondary-fixed dark:text-amber-200">{routingState.error}</p>
                    ) : null}
                    <p className="text-xs text-on-secondary-fixed-variant dark:text-slate-400 leading-snug">{routingNarrative}</p>
                    <div className="text-[10px] font-bold text-on-secondary-fixed dark:text-slate-300">
                      {doiContact.name || 'State Department of Insurance'} · enrichment fallback
                    </div>
                  </div>
                )}
              </div>
              <span className="material-symbols-outlined absolute -bottom-6 -right-6 text-7xl text-on-secondary-container/10 dark:text-slate-600/40 pointer-events-none">
                policy
              </span>
            </div>
            </div>
          </aside>
        </div>
        </div>
      </main>

      <Footer disclaimer="Resolvly is not a law firm. Information provided does not constitute legal advice. Action plans are based on algorithmic analysis of insurance denial patterns and Indiana Department of Insurance (IDOI) public records." />
    </div>
  )
}
