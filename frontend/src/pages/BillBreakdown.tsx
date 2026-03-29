import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

// ─── Demo data matching the ResultsDashboard claim ────────────────────────────

const CLAIM_META = {
  id: '#CLM2026-03284',
  patient: 'Jane Doe',
  provider: 'Dr. Sarah Chen, MD — Pain Management',
  insurer: 'Anthem Blue Cross Blue Shield',
  dateOfService: 'March 12, 2026',
  dateOfDenial: 'March 24, 2026',
}

interface LineItem {
  id: string
  code: string
  codeType: 'CPT' | 'HCPCS' | 'ICD-10'
  description: string
  plainEnglish: string
  billed: number
  allowed: number | null
  planPaid: number
  denied: number
  patientOwe: number
  denialReason: string | null
  fixable: boolean
  fixSuggestion: string | null
}

const LINE_ITEMS: LineItem[] = [
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
    codeType: 'CPT',
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

// Show only monetary line items for the table
const MONETARY_ITEMS = LINE_ITEMS.filter(i => i.billed > 0 || i.denied > 0)

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

// ─── Expandable line item row ─────────────────────────────────────────────────

function LineItemRow({ item, expanded, onToggle }: {
  item: LineItem
  expanded: boolean
  onToggle: () => void
}) {
  const isDenied = item.denied > 0
  const typeColors: Record<string, string> = {
    CPT: 'bg-purple-100 text-purple-800',
    HCPCS: 'bg-indigo-100 text-indigo-800',
    'ICD-10': 'bg-blue-100 text-blue-800',
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

  function toggleRow(id: string) {
    setExpandedRows(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function expandAll() {
    setExpandedRows(new Set(MONETARY_ITEMS.map(i => i.id)))
  }

  return (
    <div className="bg-background text-on-background min-h-screen flex flex-col">
      <Navbar />

      <main className="pt-20 pb-16 flex-grow">

        {/* Page header */}
        <div className="border-b border-slate-200 bg-white shadow-sm">
          <div className="max-w-6xl mx-auto px-6 py-8">
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
                  <p>Claim <code className="font-mono bg-slate-100 px-1 rounded">{CLAIM_META.id}</code> · {CLAIM_META.dateOfService}</p>
                  <p>Provider: {CLAIM_META.provider}</p>
                  <p>Insurer: {CLAIM_META.insurer}</p>
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
                  className="flex items-center gap-2 px-4 py-2 border border-slate-300 text-slate-600 rounded-lg text-sm font-semibold hover:bg-slate-50 transition-all"
                >
                  <span className="material-symbols-outlined text-sm">download</span>
                  Export PDF
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-6xl mx-auto px-6 pt-8 space-y-10">

          {/* Financial waterfall */}
          <section>
            <h2 className="text-xl font-bold text-on-surface mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">account_balance_wallet</span>
              Financial Summary
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Waterfall */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-0">
                {[
                  { label: 'Total Billed', value: TOTAL_BILLED, cls: 'text-on-surface', barClass: 'bg-slate-300', barPct: 100, desc: 'What the provider charged before any adjustments.' },
                  { label: 'Network Adjustment', value: -NETWORK_ADJUSTMENT, cls: 'text-slate-500', barClass: 'bg-slate-200', barPct: (NETWORK_ADJUSTMENT / TOTAL_BILLED) * 100, desc: 'Discount negotiated by your insurer with in-network providers.' },
                  { label: 'Plan Paid', value: PLAN_PAID, cls: 'text-emerald-700', barClass: 'bg-emerald-400', barPct: (PLAN_PAID / TOTAL_BILLED) * 100, desc: 'Amount your insurer paid for covered services.' },
                  { label: 'Your Copay', value: -COPAY, cls: 'text-slate-500', barClass: 'bg-amber-300', barPct: (COPAY / TOTAL_BILLED) * 100, desc: 'Fixed amount you owe per visit under your plan terms.' },
                  { label: 'Denied (Disputed)', value: DENIED_DISPUTED, cls: 'text-error font-extrabold', barClass: 'bg-red-400', barPct: (DENIED_DISPUTED / TOTAL_BILLED) * 100, desc: 'Amount denied due to missing prior authorization — subject to appeal.' },
                ].map(({ label, value, cls, barClass, barPct, desc }) => (
                  <div key={label} className="group py-4 border-b border-slate-100 last:border-0">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-sm font-semibold text-on-surface">{label}</span>
                      <span className={`text-base font-bold ${cls}`}>
                        {value < 0 ? `−${fmt(Math.abs(value))}` : fmt(value)}
                      </span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden mb-1">
                      <div className={`h-full ${barClass} rounded-full transition-all`} style={{ width: `${barPct}%` }} />
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed hidden group-hover:block">{desc}</p>
                  </div>
                ))}
              </div>

              {/* Summary cards */}
              <div className="space-y-4">
                <div className="bg-error-container border border-error/20 rounded-xl p-6">
                  <p className="text-xs font-bold text-error uppercase tracking-widest mb-1">Disputed Amount</p>
                  <p className="text-4xl font-extrabold text-error mb-2">{fmt(DENIED_DISPUTED)}</p>
                  <p className="text-sm text-on-error-container leading-relaxed">
                    This is the amount denied for CPT 62323 due to missing prior authorization. This is the most likely amount you can recover through appeal.
                  </p>
                  <div className="mt-4 flex items-center gap-2">
                    <span className="material-symbols-outlined text-emerald-600 text-sm">trending_up</span>
                    <span className="text-xs font-bold text-emerald-700">78% appeal success rate for this denial type</span>
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">Responsibility Breakdown</p>
                  {[
                    { party: 'Your Insurer (Anthem)', amount: PLAN_PAID, color: 'bg-primary', pct: Math.round((PLAN_PAID / TOTAL_BILLED) * 100) },
                    { party: 'You (patient)', amount: PATIENT_RESPONSIBILITY, color: 'bg-amber-400', pct: Math.round((PATIENT_RESPONSIBILITY / TOTAL_BILLED) * 100) },
                    { party: 'Disputed / Denied', amount: DENIED_DISPUTED, color: 'bg-error', pct: Math.round((DENIED_DISPUTED / TOTAL_BILLED) * 100) },
                  ].map(({ party, amount, color, pct }) => (
                    <div key={party} className="flex items-center gap-3 mb-3">
                      <div className={`w-3 h-3 rounded-full shrink-0 ${color}`} />
                      <span className="text-sm text-on-surface flex-1">{party}</span>
                      <span className="text-sm font-bold text-on-surface">{fmt(amount)}</span>
                      <span className="text-xs text-slate-400 w-8 text-right">{pct}%</span>
                    </div>
                  ))}
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
                  <h3 className="text-sm font-bold text-primary mb-2 flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">lightbulb</span>
                    What You Should Do
                  </h3>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    Contact Dr. Sarah Chen's billing office at{' '}
                    <a href="tel:3175550142" className="text-primary font-bold hover:underline">(317) 555-0142</a>{' '}
                    and ask them to submit a retroactive prior authorization request for CPT 62323. Provide the clinical notes from the March 12th visit.
                  </p>
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
                    {MONETARY_ITEMS.map(item => (
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
                      <td className="px-4 py-4 text-right text-sm font-extrabold text-on-surface">{fmt(TOTAL_BILLED)}</td>
                      <td className="px-4 py-4 text-right text-sm font-bold text-on-surface-variant">{fmt(120)}</td>
                      <td className="px-4 py-4 text-right text-sm font-bold text-emerald-700">{fmt(PLAN_PAID)}</td>
                      <td className="px-4 py-4 text-right text-sm font-extrabold text-error">{fmt(DENIED_DISPUTED)}</td>
                      <td className="px-4 py-4 text-right text-sm font-bold text-on-surface">{fmt(PATIENT_RESPONSIBILITY)}</td>
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white border border-red-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-3">
                  <code className="font-mono text-base font-bold bg-red-100 border border-red-300 px-3 py-1 rounded-lg text-red-900">
                    CARC CO-197
                  </code>
                  <span className="text-xs text-slate-500 font-semibold uppercase tracking-widest">Primary Denial</span>
                </div>
                <p className="text-sm font-semibold text-on-surface mb-2">Precertification/authorization/notification absent</p>
                <p className="text-sm text-slate-600 leading-relaxed mb-3">
                  Your insurer required prior approval before performing this procedure. That approval was not on file at the time of the claim.
                </p>
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                  <p className="text-xs font-bold text-emerald-800 mb-1">Fix: Retroactive Authorization</p>
                  <p className="text-xs text-emerald-700 leading-relaxed">
                    This is one of the most reversible denial types. Contact your provider's billing office to submit a retroactive prior auth request.
                  </p>
                </div>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Source Reference</p>
                  <p className="text-sm text-slate-700 leading-relaxed mb-3">
                    CARC codes are part of the X12 EDI transaction set and are maintained by the Washington Publishing Company (WPC) under CMS oversight.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/indiana-resources/code-lookup')}
                  className="flex items-center gap-2 text-sm font-bold text-primary hover:underline"
                >
                  <span className="material-symbols-outlined text-sm">search</span>
                  Look up this code in detail
                </button>
              </div>
            </div>
          </section>

          {/* CTA bar */}
          <div className="bg-primary rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between gap-6">
            <div>
              <h3 className="text-xl font-bold text-on-primary mb-1">Ready to fight this denial?</h3>
              <p className="text-on-primary/80 text-sm">
                Your appeal success odds are <strong className="text-on-primary">78%</strong>. The Action Plan has your step-by-step roadmap.
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
      </main>

      <Footer disclaimer="Resolvly is not a law firm. Bill breakdown data is extracted from submitted documents and enriched with CMS code definitions for informational purposes only." />
    </div>
  )
}
