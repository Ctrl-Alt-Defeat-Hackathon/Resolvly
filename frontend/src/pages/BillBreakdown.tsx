import { useState, useMemo, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { analysisBundleFingerprint, loadAnalysisBundle } from '../lib/sessionKeys'
import { getCodeLookup, postExportPdf } from '../lib/api'
import { getCachedProbability, getCachedSummary } from '../lib/outputsCache'
import {
  buildDenialCards,
  buildLineItemsFromClaim,
  claimMetaFromBundle,
  formatCarcLabel,
  type BillLineItem,
  type DenialCodeCard,
  type EnrichmentCodeEntry,
} from '../lib/billBreakdownFromBundle'
import { parseMoney } from '../lib/parseMoney'

// ─── Demo data matching the ResultsDashboard claim ────────────────────────────

const CLAIM_META = {
  id: '#CLM2026-03284',
  patient: 'Jane Doe',
  provider: 'Dr. Sarah Chen, MD — Pain Management',
  insurer: 'Anthem Blue Cross Blue Shield',
  dateOfService: 'March 12, 2026',
  dateOfDenial: 'March 24, 2026',
}

const LINE_ITEMS: BillLineItem[] = [
  {
    id: '1',
    code: 'CPT 62323',
    codeType: 'CPT',
    description: 'Injection(s), of diagnostic or therapeutic substance(s) — lumbar or sacral (caudal)',
    plainEnglish: 'A steroid injection into the lower back to relieve chronic pain. This is the main procedure that was performed.',
    billed: 4250.00,
    allowed: 0,
    planPaid: 0,
    denied: 4250.00,
    patientOwe: 0,
    denialReason: 'Prior authorization not obtained (CARC CO-197)',
    fixable: true,
    fixSuggestion: 'Provider can submit a retroactive prior authorization request with clinical notes documenting medical necessity.',
  },
  {
    id: '2',
    code: 'CPT 99213',
    codeType: 'CPT',
    description: 'Office or other outpatient visit — established patient, low-to-moderate complexity',
    plainEnglish: 'A standard follow-up office visit with the doctor before the procedure.',
    billed: 185.00,
    allowed: 120.00,
    planPaid: 96.00,
    denied: 0,
    patientOwe: 24.00,
    denialReason: null,
    fixable: false,
    fixSuggestion: null,
  },
  {
    id: '3',
    code: 'ICD-10 M54.5',
    codeType: 'ICD-10',
    description: 'Low back pain',
    plainEnglish: 'The diagnosis code that explains why the injection was medically necessary.',
    billed: 0,
    allowed: 0,
    planPaid: 0,
    denied: 0,
    patientOwe: 0,
    denialReason: null,
    fixable: false,
    fixSuggestion: null,
  },
  {
    id: '4',
    code: 'CARC CO-197',
    codeType: 'CARC',
    description: 'Precertification/authorization/notification absent',
    plainEnglish: 'Your insurer required your provider to get pre-approval before doing this procedure. That approval was not on file.',
    billed: 0,
    allowed: 0,
    planPaid: 0,
    denied: 4250.00,
    patientOwe: 0,
    denialReason: 'This is the denial reason code applied to CPT 62323.',
    fixable: true,
    fixSuggestion: 'This is a procedural denial — one of the most fixable types. Request retroactive authorization from your provider.',
  },
]

// Show only monetary line items for the table (default table rows)
const MONETARY_ITEMS_DEFAULT = LINE_ITEMS.filter(i => i.billed > 0 || i.denied > 0)

// ─── Waterfall summary ────────────────────────────────────────────────────────

const TOTAL_BILLED = 4435.00
const NETWORK_ADJUSTMENT = 65.00       // Billed - (allowed + full denied)
const PLAN_PAID = 96.00
const COPAY = 24.00
const DENIED_DISPUTED = 4250.00
const PATIENT_RESPONSIBILITY = COPAY  // excluding disputed

function fmt(n: number) {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function fmtOpt(n: number | null) {
  return n === null || Number.isNaN(n) ? '—' : fmt(n)
}

// ─── Expandable line item row ─────────────────────────────────────────────────

function LineItemRow({ item, expanded, onToggle }: {
  item: BillLineItem
  expanded: boolean
  onToggle: () => void
}) {
  const isDenied = item.denied > 0
  const typeColors: Record<string, string> = {
    CPT: 'bg-purple-100 text-purple-800',
    HCPCS: 'bg-indigo-100 text-indigo-800',
    'ICD-10': 'bg-blue-100 text-blue-800',
    CARC: 'bg-red-100 text-red-900',
  }

  return (
    <>
      <tr
        className={`border-b border-slate-100 cursor-pointer hover:bg-slate-50 transition-colors
          ${isDenied ? 'bg-red-50/40' : ''}`}
        onClick={onToggle}
      >
        <td className="px-4 py-4">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${typeColors[item.codeType] ?? 'bg-slate-100 text-slate-700'}`}>
              {item.codeType}
            </span>
            <code className="font-mono text-sm font-bold text-on-surface">{item.code}</code>
          </div>
          <p className="text-xs text-on-surface-variant mt-0.5 max-w-xs truncate">{item.description}</p>
        </td>
        <td className="px-4 py-4 text-right text-sm font-semibold text-on-surface">{fmt(item.billed)}</td>
        <td className="px-4 py-4 text-right text-sm text-on-surface-variant">{item.allowed !== null ? fmt(item.allowed) : '—'}</td>
        <td className="px-4 py-4 text-right text-sm text-emerald-700 font-semibold">{item.planPaid > 0 ? fmt(item.planPaid) : '—'}</td>
        <td className="px-4 py-4 text-right">
          {item.denied > 0
            ? <span className="text-sm font-bold text-error">{fmt(item.denied)}</span>
            : <span className="text-sm text-slate-300">—</span>}
        </td>
        <td className="px-4 py-4 text-right text-sm font-semibold text-on-surface">{item.patientOwe > 0 ? fmt(item.patientOwe) : '—'}</td>
        <td className="px-4 py-4 text-center">
          <span className="material-symbols-outlined text-sm text-on-surface-variant transition-transform"
            style={{ display: 'inline-block', transform: expanded ? 'rotate(180deg)' : 'none' }}>
            expand_more
          </span>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-100">
          <td colSpan={7} className="px-4 pb-5 pt-1">
            <div className="bg-slate-50 rounded-xl p-5 ml-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-bold text-primary uppercase tracking-widest mb-1">Plain English</p>
                  <p className="text-sm text-slate-700 leading-relaxed">{item.plainEnglish}</p>
                </div>
                {item.denialReason && (
                  <div>
                    <p className="text-xs font-bold text-error uppercase tracking-widest mb-1">Why Denied</p>
                    <p className="text-sm text-slate-700 leading-relaxed">{item.denialReason}</p>
                  </div>
                )}
              </div>
              {item.fixable && item.fixSuggestion && (
                <div className="flex items-start gap-3 bg-emerald-50 border border-emerald-200 rounded-lg p-4">
                  <span className="material-symbols-outlined text-emerald-600 shrink-0">tips_and_updates</span>
                  <div>
                    <p className="text-xs font-bold text-emerald-800 uppercase tracking-widest mb-1">How to Fix This</p>
                    <p className="text-sm text-emerald-800 leading-relaxed">{item.fixSuggestion}</p>
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function BillBreakdown() {
  const navigate = useNavigate()
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  /** CARC/RARC (and any) details merged from GET /api/v1/codes/lookup when missing in analyze enrichment */
  const [fetchedCodeDetails, setFetchedCodeDetails] = useState<Record<string, EnrichmentCodeEntry>>({})
  /** Live copy from POST /api/v1/outputs/summary + /outputs/probability */
  const [apiPanels, setApiPanels] = useState<{
    loading: boolean
    summaryText: string
    keyPoints: string[]
    probPct: number | null
    probInterpretation: string
  }>({ loading: false, summaryText: '', keyPoints: [], probPct: null, probInterpretation: '' })

  const bundleFingerprint = analysisBundleFingerprint()
  const bundle = useMemo(() => loadAnalysisBundle(), [bundleFingerprint])

  const enrichmentCodes = useMemo((): Record<string, EnrichmentCodeEntry> => {
    const base = (bundle?.enrichment?.codes ?? {}) as Record<string, EnrichmentCodeEntry>
    return { ...base, ...fetchedCodeDetails }
  }, [bundle, fetchedCodeDetails])

  useEffect(() => {
    setFetchedCodeDetails({})
    if (!bundle?.claim_object) return
    const denial = (bundle.claim_object.denial_reason ?? {}) as Record<string, unknown>
    const carcs = (denial.carc_codes as string[]) ?? []
    const rarcs = (denial.rarc_codes as string[]) ?? []
    const base = (bundle.enrichment?.codes ?? {}) as Record<string, EnrichmentCodeEntry>
    const needCarc = carcs.filter(raw => raw && !base[raw]?.description)
    const needRarc = rarcs.filter(raw => raw && !base[raw]?.description)
    if (needCarc.length === 0 && needRarc.length === 0) return

    let cancelled = false
    ;(async () => {
      const additions: Record<string, EnrichmentCodeEntry> = {}
      for (const raw of needCarc) {
        try {
          const r = await getCodeLookup(raw, 'carc')
          if (cancelled) return
          additions[raw] = {
            code: r.code,
            code_type: r.code_type,
            description: r.description,
            plain_english: r.plain_english,
            common_fix: r.common_fix,
            found: r.found,
          }
        } catch {
          /* keep UI on enrichment-only data */
        }
      }
      for (const raw of needRarc) {
        try {
          const r = await getCodeLookup(raw, 'rarc')
          if (cancelled) return
          additions[raw] = {
            code: r.code,
            code_type: r.code_type,
            description: r.description,
            plain_english: r.plain_english,
            common_fix: r.common_fix,
            found: r.found,
          }
        } catch {
          /* ignore */
        }
      }
      if (!cancelled && Object.keys(additions).length > 0) {
        setFetchedCodeDetails(additions)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [bundle])

  useEffect(() => {
    if (!bundle?.claim_object) {
      setApiPanels({ loading: false, summaryText: '', keyPoints: [], probPct: null, probInterpretation: '' })
      return
    }
    let cancelled = false
    setApiPanels(s => ({ ...s, loading: true }))
    Promise.all([
      getCachedSummary(bundle.claim_object, bundle.analysis, bundle.enrichment),
      getCachedProbability(bundle.claim_object, bundle.analysis, bundle.enrichment),
    ])
      .then(([sum, prob]) => {
        if (cancelled) return
        setApiPanels({
          loading: false,
          summaryText: String(sum.summary_text ?? '').trim(),
          keyPoints: Array.isArray(sum.key_points) ? sum.key_points.map(String) : [],
          probPct: typeof prob.score === 'number' ? Math.round(prob.score * 100) : null,
          probInterpretation: String(prob.interpretation ?? '').trim(),
        })
      })
      .catch(() => {
        if (!cancelled) {
          setApiPanels({ loading: false, summaryText: '', keyPoints: [], probPct: null, probInterpretation: '' })
        }
      })
    return () => {
      cancelled = true
    }
  }, [bundleFingerprint])

  const derived = useMemo(() => {
    if (!bundle?.claim_object) {
      const demoPool = PLAN_PAID + PATIENT_RESPONSIBILITY + DENIED_DISPUTED
      return {
        claimMeta: CLAIM_META,
        totalBilled: TOTAL_BILLED,
        networkAdjustment: NETWORK_ADJUSTMENT,
        planPaid: PLAN_PAID,
        copay: COPAY,
        deniedDisputed: DENIED_DISPUTED,
        patientResponsibility: PATIENT_RESPONSIBILITY,
        allowedSum: 120,
        prob: 78,
        lineItems: LINE_ITEMS,
        tableItems: MONETARY_ITEMS_DEFAULT,
        denialCards: [] as DenialCodeCard[],
        disputedBlurb:
          'Sample amounts for layout preview. Complete Analyze from the home flow to load your extracted claim and live API summaries.',
        actionBlurb: '',
        appealsPhone: '',
        insurerShortLabel: 'Your insurer',
        chartBase: Math.max(TOTAL_BILLED, 1),
        pctPlan: demoPool > 0 ? Math.round((PLAN_PAID / demoPool) * 100) : 0,
        pctPatient: demoPool > 0 ? Math.round((PATIENT_RESPONSIBILITY / demoPool) * 100) : 0,
        pctDenied: demoPool > 0 ? Math.round((DENIED_DISPUTED / demoPool) * 100) : 0,
      }
    }
    const c = bundle.claim_object as Record<string, unknown>
    const fin = (c.financial ?? {}) as Record<string, unknown>
    const service = (c.service_billing ?? {}) as Record<string, unknown>
    const denial = (c.denial_reason ?? {}) as Record<string, unknown>
    const appeal = (c.appeal_rights ?? {}) as Record<string, unknown>
    const analysis = (bundle.analysis ?? {}) as Record<string, unknown>
    const ap = (analysis.approval_probability ?? {}) as Record<string, unknown>
    // StoredAnalysisBundle only — populated by POST /documents/extract + POST /claims/analyze (OCR/LLM there, not on this page).
    // Do not fall back to demo constants when fields are missing; that looked like "stuck" sample data.
    const totalBilled = parseMoney(fin.billed_amount)
    const planPaid = parseMoney(fin.insurer_paid_amount)
    const deniedDisputed = parseMoney(fin.denied_amount)
    const copay = parseMoney(fin.copay_amount)
    const patientResponsibility = parseMoney(fin.patient_responsibility_total) ?? copay ?? null
    const allowedSum = parseMoney(fin.allowed_amount)
    const tbNum = totalBilled ?? 0
    const chartBase = Math.max(
      tbNum,
      planPaid ?? 0,
      deniedDisputed ?? 0,
      copay ?? 0,
      patientResponsibility ?? 0,
      1
    )
    const networkAdjustment = Math.max(
      0,
      tbNum -
        (planPaid ?? 0) -
        (deniedDisputed ?? 0) -
        (patientResponsibility ?? 0)
    )
    const prob = typeof ap.score === 'number' ? Math.round(ap.score * 100) : 78
    const claimMeta = claimMetaFromBundle(c, {
      ...CLAIM_META,
      insurer: 'Your health plan (from your documents)',
    })
    const lineItems = buildLineItemsFromClaim(c, enrichmentCodes, analysis)
    const tableItems = lineItems.filter(
      i => i.billed > 0 || i.denied > 0 || i.codeType === 'ICD-10' || i.codeType === 'CARC'
    )
    const denialCards = buildDenialCards(c, enrichmentCodes)
    const procHint = String(service.procedure_description || 'the denied service').trim()
    const firstCarcRaw =
      Array.isArray(denial.carc_codes) && denial.carc_codes.length ? String(denial.carc_codes[0]) : ''
    const firstCarcLabel = firstCarcRaw ? formatCarcLabel(firstCarcRaw) : 'the adjustment code on your EOB'
    const disputedBlurb =
      deniedDisputed === null
        ? 'No denied balance was found in extraction.'
        : deniedDisputed > 0
          ? `This is the amount your plan disputed or denied${procHint ? ` for ${procHint}` : ''}. Denial codes such as ${firstCarcLabel} are explained below.`
          : 'No disputed balance was recorded for this claim.'
    const phone = typeof appeal.insurer_appeals_phone === 'string' ? appeal.insurer_appeals_phone.trim() : ''
    const prov = String((c.patient_provider as Record<string, unknown>)?.treating_provider_name || 'your provider').trim()
    const actionBlurb = phone
      ? `Call your plan’s appeals line at ${phone} to confirm next steps. Ask ${prov || 'your provider'}’s billing office to help with documentation or retroactive authorization if applicable.`
      : `Contact ${prov || 'your provider'}’s billing office using the number on your bill or EOB, and use your plan’s member services number for appeals — both are usually printed on your denial or EOB.`

    const responsibilityPool = (planPaid ?? 0) + (patientResponsibility ?? 0) + (deniedDisputed ?? 0)
    const pool = responsibilityPool > 0 ? responsibilityPool : 1
    const pctPlan = Math.round(((planPaid ?? 0) / pool) * 100)
    const pctPatient = Math.round(((patientResponsibility ?? 0) / pool) * 100)
    const pctDenied = Math.round(((deniedDisputed ?? 0) / pool) * 100)

    return {
      claimMeta,
      totalBilled,
      networkAdjustment,
      planPaid,
      copay,
      deniedDisputed,
      patientResponsibility,
      allowedSum,
      prob,
      lineItems,
      tableItems,
      denialCards,
      disputedBlurb,
      actionBlurb,
      appealsPhone: phone,
      insurerShortLabel: 'Your health plan',
      chartBase,
      pctPlan,
      pctPatient,
      pctDenied,
    }
  }, [bundle, enrichmentCodes])

  function toggleRow(id: string) {
    setExpandedRows(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function expandAll() {
    setExpandedRows(new Set(derived.tableItems.map(i => i.id)))
  }

  async function exportPdf() {
    const md = `# Bill breakdown\n\nClaim: ${derived.claimMeta.id}\nProvider: ${derived.claimMeta.provider}\n`
    try {
      const blob = await postExportPdf({ content: md, format: 'summary', title: 'Bill breakdown' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 'bill-breakdown.pdf'
      a.click()
      URL.revokeObjectURL(a.href)
    } catch {
      /* silent */
    }
  }

  return (
    <div className="bg-background text-on-background selection:bg-secondary-container min-h-screen flex flex-col">
      <Navbar />

      <main className="pt-24 pb-12 flex-grow">
        <div className="editorial-margin">
        {/* Page header */}
        <div className="border-b border-slate-200 bg-white shadow-sm">
          <div className="py-8">
            <nav className="flex items-center gap-2 text-xs text-slate-400 mb-4 font-medium uppercase tracking-widest">
              <Link to="/action-plan" className="hover:text-primary transition-colors">Action Plan</Link>
              <span className="material-symbols-outlined text-sm">chevron_right</span>
              <span className="text-primary font-bold">Bill Breakdown</span>
            </nav>
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
              <div>
                <h1 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight mb-2">
                  Bill Breakdown Explainer
                </h1>
                <div className="text-sm text-slate-600 space-y-0.5">
                  <p>Claim <code className="font-mono bg-slate-100 px-1 rounded">{derived.claimMeta.id}</code> · {derived.claimMeta.dateOfService}</p>
                  <p>Provider: {derived.claimMeta.provider}</p>
                  <p>Insurer: {derived.claimMeta.insurer}</p>
                </div>
              </div>
              <div className="flex gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => navigate('/appeal-drafting')}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:opacity-90 transition-all"
                >
                  <span className="material-symbols-outlined text-sm">edit_document</span>
                  Draft Appeal
                </button>
                <button
                  type="button"
                  onClick={() => void exportPdf()}
                  className="flex items-center gap-2 px-4 py-2 border border-slate-300 text-slate-600 rounded-lg text-sm font-semibold hover:bg-slate-50 transition-all"
                >
                  <span className="material-symbols-outlined text-sm">download</span>
                  Export PDF
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="pt-8 space-y-10">

          {/* Financial waterfall */}
          <section>
            <h2 className="text-xl font-bold text-on-surface mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">account_balance_wallet</span>
              Financial Summary
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Waterfall */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-0">
                {([
                  {
                    label: 'Total Billed',
                    raw: derived.totalBilled as number | null,
                    neg: false,
                    cls: 'text-on-surface',
                    barClass: 'bg-slate-300',
                    barPct: () => 100,
                    desc: 'What the provider charged before any adjustments.',
                  },
                  {
                    label: 'Network Adjustment',
                    raw: -derived.networkAdjustment,
                    neg: true,
                    cls: 'text-slate-500',
                    barClass: 'bg-slate-200',
                    barPct: () => (Math.abs(derived.networkAdjustment) / derived.chartBase) * 100,
                    desc: 'Discount negotiated by your insurer with in-network providers.',
                  },
                  {
                    label: 'Plan Paid',
                    raw: derived.planPaid as number | null,
                    neg: false,
                    cls: 'text-emerald-700',
                    barClass: 'bg-emerald-400',
                    barPct: (_r: number | null) => ((derived.planPaid ?? 0) / derived.chartBase) * 100,
                    desc: 'Amount your insurer paid for covered services.',
                  },
                  {
                    label: 'Your Copay',
                    raw: derived.copay === null ? null : -derived.copay,
                    neg: true,
                    cls: 'text-slate-500',
                    barClass: 'bg-amber-300',
                    barPct: (_r: number | null) => ((derived.copay ?? 0) / derived.chartBase) * 100,
                    desc: 'Fixed amount you owe per visit under your plan terms.',
                  },
                  {
                    label: 'Denied (Disputed)',
                    raw: derived.deniedDisputed as number | null,
                    neg: false,
                    cls: 'text-error font-extrabold',
                    barClass: 'bg-red-400',
                    barPct: (_r: number | null) => ((derived.deniedDisputed ?? 0) / derived.chartBase) * 100,
                    desc: 'Amount your plan did not pay — often subject to internal appeal or external review.',
                  },
                ] as const).map(row => {
                  const display =
                    row.raw === null || Number.isNaN(row.raw)
                      ? '—'
                      : row.neg && row.raw < 0
                        ? `−${fmt(Math.abs(row.raw))}`
                        : fmt(row.raw)
                  const bp =
                    typeof row.barPct === 'function'
                      ? row.barPct.length > 0
                        ? (row.barPct as (r: number | null) => number)(row.raw as number | null)
                        : (row.barPct as () => number)()
                      : 0
                  return (
                    <div key={row.label} className="group py-4 border-b border-slate-100 last:border-0">
                      <div className="flex justify-between items-center mb-1.5 gap-2">
                        <span className="text-sm font-semibold text-on-surface">{row.label}</span>
                        <span className={`text-base font-bold ${row.cls} ${row.raw === null ? 'text-slate-400 font-normal' : ''}`}>
                          {display}
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden mb-1">
                        <div className={`h-full ${row.barClass} rounded-full transition-all`} style={{ width: `${Math.min(bp, 100)}%` }} />
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed hidden group-hover:block">{row.desc}</p>
                    </div>
                  )
                })}
              </div>

              {/* Summary cards */}
              <div className="space-y-4">
                <div className="bg-error-container border border-error/20 rounded-xl p-6">
                  <p className="text-xs font-bold text-error uppercase tracking-widest mb-1">Disputed Amount</p>
                  <p className="text-4xl font-extrabold text-error mb-2">{fmtOpt(derived.deniedDisputed as number | null)}</p>
                  {apiPanels.loading && bundle?.claim_object && (
                    <div className="space-y-2 mb-3">
                      <div className="h-3 bg-error/10 rounded animate-pulse w-full" />
                      <div className="h-3 bg-error/10 rounded animate-pulse w-[92%]" />
                      <div className="h-3 bg-error/10 rounded animate-pulse w-4/5" />
                    </div>
                  )}
                  {!apiPanels.loading && apiPanels.summaryText && bundle?.claim_object && (
                    <p className="text-sm text-on-error-container leading-relaxed mb-3 whitespace-pre-wrap">
                      {apiPanels.summaryText}
                    </p>
                  )}
                  {(!bundle?.claim_object || (!apiPanels.loading && !apiPanels.summaryText)) && (
                    <p className="text-sm text-on-error-container leading-relaxed mb-3">{derived.disputedBlurb}</p>
                  )}
                  <div className="mt-4 flex items-center gap-2">
                    <span className="material-symbols-outlined text-emerald-600 text-sm">trending_up</span>
                    <span className="text-xs font-bold text-emerald-700">
                      {(apiPanels.probPct ?? derived.prob) != null
                        ? `${apiPanels.probPct ?? derived.prob}% estimated appeal outlook`
                        : '—'}
                      {apiPanels.probInterpretation ? ` — ${apiPanels.probInterpretation}` : ''}
                    </span>
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">Responsibility Breakdown</p>
                  {[
                    { party: derived.insurerShortLabel, amount: derived.planPaid, color: 'bg-primary', pct: derived.pctPlan },
                    { party: 'You (patient)', amount: derived.patientResponsibility, color: 'bg-amber-400', pct: derived.pctPatient },
                    { party: 'Disputed / Denied', amount: derived.deniedDisputed, color: 'bg-error', pct: derived.pctDenied },
                  ].map(({ party, amount, color, pct }) => (
                    <div key={party} className="flex items-center gap-3 mb-3">
                      <div className={`w-3 h-3 rounded-full shrink-0 ${color}`} />
                      <span className="text-sm text-on-surface flex-1">{party}</span>
                      <span className="text-sm font-bold text-on-surface">{fmtOpt(amount as number | null)}</span>
                      <span className="text-xs text-slate-400 w-8 text-right">{pct}%</span>
                    </div>
                  ))}
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
                  <h3 className="text-sm font-bold text-primary mb-2 flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">lightbulb</span>
                    What You Should Do
                  </h3>
                  {apiPanels.loading && bundle?.claim_object && (
                    <div className="space-y-2 mb-3">
                      <div className="h-3 bg-slate-200 rounded animate-pulse w-full" />
                      <div className="h-3 bg-slate-200 rounded animate-pulse w-[83%]" />
                    </div>
                  )}
                  {!apiPanels.loading && apiPanels.keyPoints.length > 0 && bundle?.claim_object && (
                    <ul className="text-sm text-slate-700 list-disc list-inside mb-3 space-y-1">
                      {apiPanels.keyPoints.slice(0, 3).map((k, i) => (
                        <li key={i}>{k}</li>
                      ))}
                    </ul>
                  )}
                  <p className="text-sm text-slate-700 leading-relaxed">{derived.actionBlurb}</p>
                  <button
                    type="button"
                    onClick={() => navigate('/action-plan')}
                    className="mt-3 text-xs font-bold text-primary hover:underline flex items-center gap-1"
                  >
                    View full action plan <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* Line items table */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-on-surface flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">receipt_long</span>
                Itemized Line Items
              </h2>
              <button
                type="button"
                onClick={expandAll}
                className="text-xs font-bold text-primary hover:underline flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-sm">unfold_more</span>
                Expand all
              </button>
            </div>
            <p className="text-sm text-slate-500 mb-4">Click any row for a plain-English explanation and fix suggestion.</p>

            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[700px]">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50">
                      {['Code / Description', 'Billed', 'Allowed', 'Plan Paid', 'Denied', 'You Owe', ''].map(h => (
                        <th key={h} className={`px-4 py-3 text-xs font-bold text-slate-500 uppercase tracking-widest ${h === 'Code / Description' ? 'text-left' : 'text-right'}`}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {derived.tableItems.map(item => (
                      <LineItemRow
                        key={item.id}
                        item={item}
                        expanded={expandedRows.has(item.id)}
                        onToggle={() => toggleRow(item.id)}
                      />
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-slate-50 border-t-2 border-slate-300">
                      <td className="px-4 py-4 text-sm font-extrabold text-on-surface">TOTALS</td>
                      <td className="px-4 py-4 text-right text-sm font-extrabold text-on-surface">{fmtOpt(derived.totalBilled as number | null)}</td>
                      <td className="px-4 py-4 text-right text-sm font-bold text-on-surface-variant">{fmtOpt(derived.allowedSum as number | null)}</td>
                      <td className="px-4 py-4 text-right text-sm font-bold text-emerald-700">{fmtOpt(derived.planPaid as number | null)}</td>
                      <td className="px-4 py-4 text-right text-sm font-extrabold text-error">{fmtOpt(derived.deniedDisputed as number | null)}</td>
                      <td className="px-4 py-4 text-right text-sm font-bold text-on-surface">{fmtOpt(derived.patientResponsibility as number | null)}</td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          </section>

          {/* Denial codes section */}
          <section>
            <h2 className="text-xl font-bold text-on-surface mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-error">cancel</span>
              Denial Codes Decoded
            </h2>
            {derived.denialCards.length === 0 && bundle?.claim_object && (
              <p className="text-sm text-slate-600 mb-4">
                No CARC/RARC codes were extracted from your documents. Upload a denial letter or EOB that lists adjustment codes so we can decode them here.
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-4">
                {derived.denialCards.map(card => (
                  <div
                    key={`${card.kind}-${card.raw}`}
                    className={`bg-white rounded-xl p-6 shadow-sm border ${card.isPrimary ? 'border-red-200' : 'border-slate-200'}`}
                  >
                    <div className="flex items-center gap-3 mb-3 flex-wrap">
                      <code className="font-mono text-base font-bold bg-red-100 border border-red-300 px-3 py-1 rounded-lg text-red-900">
                        {card.kind.toUpperCase()} {card.raw}
                      </code>
                      {card.isPrimary && (
                        <span className="text-xs text-slate-500 font-semibold uppercase tracking-widest">Primary</span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-on-surface mb-2">{card.title}</p>
                    <p className="text-sm text-slate-600 leading-relaxed mb-3">
                      {card.plainEnglish || card.description}
                    </p>
                    {card.commonFix ? (
                      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                        <p className="text-xs font-bold text-emerald-800 mb-1">Suggested next step</p>
                        <p className="text-xs text-emerald-700 leading-relaxed">{card.commonFix}</p>
                      </div>
                    ) : null}
                  </div>
                ))}
                {derived.denialCards.length === 0 && !bundle?.claim_object && (
                  <div className="bg-white border border-red-200 rounded-xl p-6 shadow-sm">
                    <div className="flex items-center gap-3 mb-3">
                      <code className="font-mono text-base font-bold bg-red-100 border border-red-300 px-3 py-1 rounded-lg text-red-900">
                        CARC CO-197
                      </code>
                      <span className="text-xs text-slate-500 font-semibold uppercase tracking-widest">Sample</span>
                    </div>
                    <p className="text-sm font-semibold text-on-surface mb-2">Precertification/authorization/notification absent</p>
                    <p className="text-sm text-slate-600 leading-relaxed mb-3">
                      Example denial: prior approval was required and was not on file. Run a full analysis to replace this with your real codes.
                    </p>
                  </div>
                )}
              </div>
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Source Reference</p>
                  <p className="text-sm text-slate-700 leading-relaxed mb-3">
                    CARC/RARC codes come from the X12 EDI transaction set and reference materials maintained under CMS oversight. Resolvly matches codes to authoritative descriptions during analysis.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/code-lookup')}
                  className="flex items-center gap-2 text-sm font-bold text-primary hover:underline"
                >
                  <span className="material-symbols-outlined text-sm">search</span>
                  Open code lookup library
                </button>
              </div>
            </div>
          </section>

          {/* CTA bar */}
          <div className="bg-primary rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between gap-6">
            <div>
              <h3 className="text-xl font-bold text-on-primary mb-1">Ready to fight this denial?</h3>
              <p className="text-on-primary/80 text-sm">
                Your appeal success odds are{' '}
                <strong className="text-on-primary">{apiPanels.probPct ?? derived.prob}%</strong>. The Action Plan has your step-by-step roadmap.
              </p>
            </div>
            <div className="flex gap-3 shrink-0">
              <button
                type="button"
                onClick={() => navigate('/appeal-drafting')}
                className="px-6 py-3 bg-white text-primary font-bold rounded-xl shadow-lg hover:scale-105 transition-transform text-sm"
              >
                Draft Appeal Letter
              </button>
              <button
                type="button"
                onClick={() => navigate('/action-plan')}
                className="px-6 py-3 bg-primary-container text-on-primary-container font-bold rounded-xl hover:opacity-90 transition-all text-sm border border-white/20"
              >
                View Action Plan
              </button>
            </div>
          </div>
        </div>
        </div>
      </main>

      <Footer disclaimer="Resolvly is not a law firm. Bill breakdown data is extracted from submitted documents and enriched with CMS code definitions for informational purposes only." />
    </div>
  )
}
