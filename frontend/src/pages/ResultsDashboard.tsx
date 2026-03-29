import { useState, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { RESOLVLY_ANALYSIS_COMPLETE_KEY } from './AnalyzeFlow'

// ─── Tab definitions ─────────────────────────────────────────────────────────
const TABS = ['Summary', 'Codes', 'Assumptions']

// ─── Shared inline code pill ─────────────────────────────────────────────────
function CodePill({ code }: { code: string }) {
  return (
    <code className="px-1.5 py-0.5 bg-slate-100 border border-slate-300 rounded text-[11px] font-mono text-slate-800">{code}</code>
  )
}

// ─── Tab: Summary ─────────────────────────────────────────────────────────────
function TabSummary() {
  return (
    <div className="space-y-8">
      {/* What Happened */}
      <section className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
        <h2 className="text-xl font-bold text-on-surface mb-4">What Happened</h2>
        <p className="text-base text-slate-800 leading-relaxed max-w-3xl">
          Your claim for a lumbar epidural steroid injection (<CodePill code="CPT 62323" />) performed by Dr. Sarah Chen on
          March 12, 2026 was denied by Anthem Blue Cross Blue Shield because prior authorization was not obtained
          before the procedure.
        </p>
        <p className="text-base text-slate-800 leading-relaxed max-w-3xl mt-4">
          The denial code <CodePill code="CARC CO-197" /> means your insurer required pre-approval for this
          procedure, and it was not on file when the claim was submitted. This is a common and often fixable issue —
          in most cases, the provider's office can request retroactive authorization.
        </p>
        <p className="text-sm text-slate-600 mt-4 max-w-3xl">
          Step-by-step tasks, deadlines, and letters are in{' '}
          <Link to="/action-plan" className="text-primary font-bold hover:underline">Action Plan</Link>
          {' '}and{' '}
          <Link to="/appeal-drafting" className="text-primary font-bold hover:underline">Appeal Drafting</Link>
          {' '}— not duplicated here.
        </p>
      </section>

      {/* 3 metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Root Cause</p>
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-primary text-2xl">key</span>
            <span className="text-lg font-bold text-on-surface">Prior Auth Missing</span>
          </div>
          <p className="text-xs text-slate-400">Confidence: 92%</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Responsible Party</p>
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-amber-500 text-2xl">local_hospital</span>
            <span className="text-lg font-bold text-on-surface">Provider's Billing Office</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">Dr. Sarah Chen, MD — Pain Management</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Approval Odds</p>
          <div className="flex items-center gap-3">
            <span className="text-4xl font-extrabold text-emerald-500">78%</span>
          </div>
          <p className="text-xs text-emerald-600 font-semibold mt-1">Likely to succeed on appeal</p>
        </div>
      </div>

      {/* Next Step */}
      <section className="bg-blue-50 border border-blue-200 rounded-xl p-6">
        <h3 className="text-lg font-bold text-primary mb-2">Your Next Step</h3>
        <p className="text-base text-slate-700 leading-relaxed">
          Call your provider's billing office at{' '}
          <a href="tel:3175550142" className="text-primary font-bold hover:underline">(317) 555-0142</a>{' '}
          and ask them to submit a retroactive prior authorization request. Open the full checklist in{' '}
          <Link to="/action-plan" className="font-bold text-primary hover:underline">Action Plan</Link>.
        </p>
      </section>
    </div>
  )
}

// ─── Tab: Codes ───────────────────────────────────────────────────────────────
const CODE_GROUPS = [
  {
    title: 'Denial Codes',
    codes: [
      {
        id: 'CARC CO-197',
        description: 'Precertification/authorization/notification absent',
        plain: 'Your insurer required your doctor to get approval before performing this procedure, and that approval was not on file when the claim was processed.',
        fix: 'Ask your provider to submit a retroactive prior authorization request to Anthem BCBS.',
        source: 'CMS X12 CARC Table',
        type: 'denial',
      },
    ],
  },
  {
    title: 'Procedure Codes',
    codes: [
      {
        id: 'CPT 62323',
        description: 'Injection(s), of diagnostic or therapeutic substance(s) (e.g., anesthetic, antispasmodic, opioid, steroid) … lumbar or sacral (caudal)',
        plain: 'A steroid injection in the lower back to treat pain. This is a common pain management procedure.',
        fix: null,
        source: 'CMS HCPCS Lookup',
        type: 'procedure',
      },
    ],
  },
  {
    title: 'Diagnosis Codes',
    codes: [
      {
        id: 'ICD-10 M54.5',
        description: 'Low back pain',
        plain: 'General lower back pain diagnosis.',
        fix: null,
        source: 'CMS ICD-10-CM',
        type: 'diagnosis',
      },
      {
        id: 'ICD-10 G89.29',
        description: 'Other chronic pain',
        plain: 'Chronic pain condition not classified elsewhere.',
        fix: null,
        source: 'CMS ICD-10-CM',
        type: 'diagnosis',
      },
    ],
  },
]

function TabCodes() {
  return (
    <div className="space-y-8">
      <p className="text-sm font-bold text-slate-500">Decoded Codes (6 found)</p>
      {CODE_GROUPS.map(group => (
        <section key={group.title}>
          <h2 className="text-lg font-bold text-on-surface mb-4">{group.title}</h2>
          <div className="space-y-4">
            {group.codes.map(code => (
              <div key={code.id} className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
                <div className="flex items-start gap-3 flex-wrap">
                  <span className="font-mono text-base font-bold bg-slate-100 border border-slate-300 px-3 py-1 rounded-lg text-slate-900">{code.id}</span>
                  <p className="text-sm text-slate-600 italic flex-1">{code.description}</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-bold text-primary uppercase tracking-widest mb-1">Plain English</p>
                    <p className="text-sm text-slate-700 leading-relaxed">{code.plain}</p>
                  </div>
                  {code.fix && (
                    <div>
                      <p className="text-xs font-bold text-emerald-600 uppercase tracking-widest mb-1">Common Fix</p>
                      <p className="text-sm text-slate-700 leading-relaxed">{code.fix}</p>
                    </div>
                  )}
                </div>
                <a href="#" className="inline-flex items-center gap-1 text-xs text-blue-600 font-semibold hover:underline">
                  <span className="material-symbols-outlined text-sm">open_in_new</span>
                  Source: {code.source}
                </a>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

// ─── Tab: Assumptions (incl. regulatory routing) ──────────────────────────────
const ASSUMPTIONS = [
  { text: 'Plan is ACA-compliant (not grandfathered)', confidence: 85 },
  { text: 'Provider is willing to submit retroactive auth', confidence: 70 },
  { text: 'This is a post-service claim', confidence: 95 },
]

function TabDetails() {
  return (
    <div className="space-y-8 max-w-3xl">
      <p className="text-sm text-slate-600">
        Itemized bill breakdown is available in{' '}
        <Link to="/action-plan" className="text-primary font-bold hover:underline">Action Plan</Link>
        {' '}so it is not repeated here.
      </p>

      {/* Assumptions */}
      <section className="bg-amber-50 border border-amber-200 rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-bold text-amber-800 flex items-center gap-2">
          <span className="material-symbols-outlined text-amber-600">warning</span>
          Assumptions &amp; Uncertainties
        </h2>
        <p className="text-sm text-amber-700">
          The following assumptions were made during analysis. If any are incorrect, results and recommendations may differ.
        </p>
        <div className="space-y-4">
          {ASSUMPTIONS.map(a => (
            <div key={a.text} className="flex items-center gap-4">
              <span className="text-xs text-slate-500 flex-1">{a.text}</span>
              <div className="flex items-center gap-2 shrink-0">
                <div className="w-20 h-1.5 bg-amber-200 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: `${a.confidence}%` }} />
                </div>
                <span className="text-xs font-bold text-amber-700 w-10 text-right">{a.confidence}%</span>
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-amber-700 flex items-start gap-1.5 pt-1">
          <span className="material-symbols-outlined text-sm shrink-0">push_pin</span>
          If your plan is grandfathered or your provider is unwilling to assist, some action steps may need to be adjusted.
        </p>
      </section>

      {/* Regulatory Routing */}
      <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-bold text-on-surface mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">balance</span>
          Regulatory Routing
        </h2>
        <p className="text-sm text-slate-600 mb-5">Your plan is regulated under: <strong>ACA + Indiana State Insurance Law</strong></p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest">Federal (ACA §2719)</h3>
            <p className="text-sm text-slate-700">Internal appeal: <strong>180 days</strong></p>
            <p className="text-sm text-slate-700">External review: <strong>4 months</strong></p>
            <div className="mt-2 space-y-1 text-xs text-slate-500">
              <p>• ACA §2719</p>
              <p>• 45 CFR §147.136</p>
            </div>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest">State (Indiana DOI)</h3>
            <a href="tel:18006224461" className="flex items-center gap-1 text-sm text-primary font-semibold hover:underline">
              <span className="material-symbols-outlined text-sm">call</span>(800) 622-4461
            </a>
            <a href="#" className="flex items-center gap-1 text-sm text-primary font-semibold hover:underline">
              <span className="material-symbols-outlined text-sm">language</span>in.gov/idoi
            </a>
            <a href="mailto:complaints@idoi.in.gov" className="flex items-center gap-1 text-sm text-primary font-semibold hover:underline">
              <span className="material-symbols-outlined text-sm">mail</span>complaints@idoi.in.gov
            </a>
            <a href="#" target="_blank" rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-white bg-primary px-3 py-1.5 rounded-lg hover:opacity-90">
              File Online <span className="material-symbols-outlined text-sm">arrow_forward</span>
            </a>
          </div>
        </div>
      </section>
    </div>
  )
}

// ─── Main ResultsDashboard ─────────────────────────────────────────────────────
type DocProfile = {
  files: { name: string; docKind: string }[]
  kindsPresent: { eob: boolean; denial: boolean; medical_bill: boolean }
}

function readDocProfile(): DocProfile | null {
  try {
    const raw = sessionStorage.getItem('resolvly_doc_profile')
    if (!raw) return null
    return JSON.parse(raw) as DocProfile
  } catch {
    return null
  }
}

export default function ResultsDashboard() {
  const [activeTab, setActiveTab] = useState(0)
  const navigate = useNavigate()

  const docProfile = useMemo(() => readDocProfile(), [])

  const TAB_CONTENT = [
    <TabSummary />,
    <TabCodes />,
    <TabDetails />,
  ]

  return (
    <div className="bg-background text-on-background min-h-screen flex flex-col">
      <Navbar />

      <main className="pt-20 pb-16 flex-grow">
        {/* Dashboard Header */}
        <div className="border-b border-slate-200 bg-white shadow-sm">
          <div className="max-w-6xl mx-auto px-6 py-8">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
              <div className="flex items-start gap-4">
                <div className="bg-amber-100 border border-amber-300 px-3 py-2 rounded-xl text-center shrink-0">
                  <p className="text-[9px] font-extrabold text-amber-800 uppercase tracking-widest">Time</p>
                  <p className="text-[9px] font-extrabold text-amber-800 uppercase tracking-widest">Sensitive</p>
                </div>
                <div>
                  <h1 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight mb-2">Claim Analysis Results</h1>
                  <div className="text-sm text-slate-600 space-y-0.5">
                    <p>Claim <code className="font-mono bg-slate-100 px-1 rounded">#CLM2026-03284</code> · Service: March 12, 2026</p>
                    <p>Provider: Dr. Sarah Chen, MD (Pain Management)</p>
                    <p>Insurer: Anthem Blue Cross Blue Shield</p>
                    <p>Denied Amount: <strong className="text-red-600">$4,250.00</strong></p>
                    {docProfile && (
                      <p className="pt-1 text-xs text-slate-500">
                        Documents in this run:{' '}
                        {[
                          docProfile.kindsPresent.denial && 'denial letter',
                          docProfile.kindsPresent.eob && 'EOB',
                          docProfile.kindsPresent.medical_bill && 'medical bill',
                        ].filter(Boolean).join(' · ') || '—'}
                      </p>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-3 shrink-0 justify-end md:items-start">
                <button className="flex items-center gap-2 px-4 py-2 border border-slate-300 text-slate-600 rounded-lg text-sm font-semibold hover:bg-slate-50 transition-all">
                  <span className="material-symbols-outlined text-sm">download</span>
                  Export Full Report
                </button>
                <button
                  type="button"
                  onClick={() => {
                    sessionStorage.removeItem(RESOLVLY_ANALYSIS_COMPLETE_KEY)
                    sessionStorage.removeItem('resolvly_doc_profile')
                    navigate('/analyze')
                  }}
                  className="flex items-center gap-2 px-4 py-2 border border-slate-300 text-slate-600 rounded-lg text-sm font-semibold hover:bg-slate-50 transition-all"
                >
                  <span className="material-symbols-outlined text-sm">refresh</span>
                  Analyze Another
                </button>
              </div>
            </div>
          </div>

          {/* Tab Bar */}
          <div className="max-w-6xl mx-auto px-6">
            <div className="flex overflow-x-auto no-scrollbar gap-0">
              {TABS.map((tab, i) => (
                <button key={tab} onClick={() => setActiveTab(i)}
                  className={`px-5 py-3 text-sm font-semibold whitespace-nowrap transition-all border-b-2 -mb-px
                    ${activeTab === i ? 'border-primary text-primary' : 'border-transparent text-slate-400 hover:text-slate-600'}`}>
                  {tab}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Tab Content */}
        <div className="max-w-6xl mx-auto px-6 pt-8">
          <div className="transition-opacity duration-200">
            {TAB_CONTENT[activeTab]}
          </div>
        </div>
      </main>

      <Footer disclaimer="Resolvly is not a law firm. Information provided does not constitute legal advice. Analysis is based on AI interpretation of submitted documents and public regulatory sources." />
    </div>
  )
}
