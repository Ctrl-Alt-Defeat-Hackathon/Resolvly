import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

// ─── Types ────────────────────────────────────────────────────────────────────

type CodeType = 'icd10' | 'cpt' | 'hcpcs' | 'carc' | 'rarc' | 'npi'

interface CodeLookupResult {
  code: string
  code_type: string
  description: string
  plain_english: string
  common_fix: string
  source: string
  source_url: string
  found: boolean
  extra: Record<string, string>
}

// ─── Code type auto-detection ─────────────────────────────────────────────────

function detectCodeType(input: string): CodeType | null {
  const s = input.trim().toUpperCase()
  if (!s) return null

  // NPI: exactly 10 digits
  if (/^\d{10}$/.test(s)) return 'npi'

  // CARC: CO-N, PR-N, OA-N, PI-N, CR-N (group prefix + digits)
  if (/^(CO|PR|OA|PI|CR)-?\d{1,3}$/i.test(s)) return 'carc'

  // RARC: starts with N or M followed by optional letters then digits, or just MA/RA prefix
  if (/^(MA|RA|N|M)[A-Z]?\d{1,4}$/i.test(s)) return 'rarc'

  // ICD-10: letter + 2 digits + optional dot + more chars (e.g. M54.5, G89.29, A01)
  if (/^[A-TV-Z]\d{2}(\.[0-9A-Z]{1,4})?$/i.test(s)) return 'icd10'

  // HCPCS: letter (A-V) + 4 digits
  if (/^[A-V]\d{4}$/i.test(s)) return 'hcpcs'

  // CPT: 5 digits
  if (/^\d{5}$/.test(s)) return 'cpt'

  return null
}

const CODE_TYPE_LABELS: Record<CodeType, string> = {
  icd10: 'ICD-10',
  cpt: 'CPT',
  hcpcs: 'HCPCS',
  carc: 'CARC',
  rarc: 'RARC',
  npi: 'NPI',
}

const CODE_TYPE_COLORS: Record<CodeType, string> = {
  icd10: 'bg-blue-100 text-blue-800 border-blue-300',
  cpt: 'bg-purple-100 text-purple-800 border-purple-300',
  hcpcs: 'bg-indigo-100 text-indigo-800 border-indigo-300',
  carc: 'bg-red-100 text-red-800 border-red-300',
  rarc: 'bg-amber-100 text-amber-800 border-amber-300',
  npi: 'bg-emerald-100 text-emerald-800 border-emerald-300',
}

// ─── Category filter buttons ──────────────────────────────────────────────────

const CATEGORIES: { icon: string; title: string; subtitle: string; type: CodeType }[] = [
  { icon: 'medical_information', title: 'ICD-10-CM', subtitle: 'Diagnostic Codes', type: 'icd10' },
  { icon: 'clinical_notes', title: 'CPT/HCPCS', subtitle: 'Procedure Tracking', type: 'cpt' },
  { icon: 'payments', title: 'CARC', subtitle: 'Claim Adjustments', type: 'carc' },
  { icon: 'receipt_long', title: 'RARC', subtitle: 'Remittance Advice', type: 'rarc' },
]

const glossaryTerms = [
  { category: 'Legal Concept', term: 'Adjudication', def: 'The formal process by which an insurance carrier determines their financial responsibility for a specific claim.' },
  { category: 'Regulatory', term: 'Clean Claim', def: 'A claim that has no defect, impropriety, or lack of any required substantiating documentation, enabling immediate processing.' },
  { category: 'Standard', term: 'Medical Necessity', def: 'Health care services that a physician, exercising prudent clinical judgment, would provide to a patient for the purposes of evaluation.' },
  { category: 'Policy', term: 'Provider Parity', def: 'The principle ensuring reimbursement rates for specialized services remain equitable across varying practitioner types.' },
]

// ─── Result card ──────────────────────────────────────────────────────────────

function ResultCard({ result, onDraftAppeal }: { result: CodeLookupResult; onDraftAppeal: () => void }) {
  const ct = result.code_type as CodeType
  const colorClass = CODE_TYPE_COLORS[ct] ?? 'bg-slate-100 text-slate-800 border-slate-300'

  if (!result.found) {
    return (
      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden">
        <div className="p-8 flex items-center gap-4">
          <span className="material-symbols-outlined text-error text-3xl">search_off</span>
          <div>
            <p className="font-bold text-on-surface">Code not found: <code className="font-mono">{result.code}</code></p>
            <p className="text-sm text-on-surface-variant mt-1">
              This code could not be resolved. Try checking the spelling or selecting the code type manually.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col md:flex-row">
        <div className="p-8 flex-1">
          <div className="flex items-center gap-3 mb-6 flex-wrap">
            <div className={`px-4 py-1.5 rounded-full font-headline font-bold text-lg border ${colorClass}`}>
              {result.code}
            </div>
            <span className="text-on-surface-variant text-sm font-semibold uppercase tracking-widest">
              {CODE_TYPE_LABELS[ct] ?? result.code_type} Code
            </span>
          </div>
          <div className="space-y-6">
            <div>
              <h4 className="text-xs font-bold text-primary uppercase tracking-widest mb-1">Official Description</h4>
              <p className="text-on-surface font-semibold text-base leading-snug">{result.description}</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {result.plain_english && (
                <div className="bg-surface-container-low p-4 rounded-lg">
                  <h4 className="text-xs font-bold text-secondary uppercase tracking-widest mb-2 flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">record_voice_over</span> Plain English
                  </h4>
                  <p className="text-sm text-on-surface-variant leading-relaxed">{result.plain_english}</p>
                </div>
              )}
              {result.common_fix && (
                <div className="bg-surface-container-low p-4 rounded-lg">
                  <h4 className="text-xs font-bold text-secondary uppercase tracking-widest mb-2 flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">build</span> Common Fix
                  </h4>
                  <p className="text-sm text-on-surface-variant leading-relaxed">{result.common_fix}</p>
                </div>
              )}
              {/* NPI provider details */}
              {ct === 'npi' && result.extra && Object.keys(result.extra).length > 0 && (
                <div className="bg-surface-container-low p-4 rounded-lg md:col-span-2">
                  <h4 className="text-xs font-bold text-secondary uppercase tracking-widest mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">badge</span> Provider Details
                  </h4>
                  <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                    {result.extra.provider_name && <><dt className="text-on-surface-variant">Name</dt><dd className="font-semibold text-on-surface">{result.extra.provider_name}</dd></>}
                    {result.extra.specialty && <><dt className="text-on-surface-variant">Specialty</dt><dd className="font-semibold text-on-surface">{result.extra.specialty}</dd></>}
                    {result.extra.provider_type && <><dt className="text-on-surface-variant">Type</dt><dd className="font-semibold text-on-surface">{result.extra.provider_type}</dd></>}
                    {result.extra.city && result.extra.state && <><dt className="text-on-surface-variant">Location</dt><dd className="font-semibold text-on-surface">{result.extra.city}, {result.extra.state} {result.extra.zip_code}</dd></>}
                    {result.extra.phone && <><dt className="text-on-surface-variant">Phone</dt><dd className="font-semibold text-on-surface">{result.extra.phone}</dd></>}
                  </dl>
                </div>
              )}
            </div>
            {result.source && (
              <a
                href={result.source_url || '#'}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-600 font-semibold hover:underline"
              >
                <span className="material-symbols-outlined text-sm">open_in_new</span>
                Source: {result.source}
              </a>
            )}
          </div>
        </div>
        {(result.common_fix || ct === 'carc' || ct === 'rarc') && (
          <div className="bg-primary p-8 md:w-64 flex flex-col justify-between shrink-0">
            <div>
              <h4 className="text-xs font-bold text-primary-fixed uppercase tracking-widest mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">tips_and_updates</span> Next Step
              </h4>
              <p className="text-on-primary text-sm leading-relaxed mb-6 font-medium">
                {result.common_fix
                  ? result.common_fix
                  : 'Use this code information to strengthen your appeal letter with precise regulatory language.'}
              </p>
            </div>
            <button
              type="button"
              onClick={onDraftAppeal}
              className="w-full bg-white text-primary py-3 rounded-xl font-headline font-bold text-sm shadow-xl hover:scale-105 transition-transform"
            >
              DRAFT APPEAL
            </button>
          </div>
        )}
      </div>

      <div className="bg-surface-container p-8 rounded-xl flex flex-col justify-between border-t-4 border-primary">
        <div>
          <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center mb-6 shadow-sm">
            <span className="material-symbols-outlined text-primary text-2xl">info</span>
          </div>
          <h3 className="font-extrabold text-xl text-primary mb-2 leading-tight">About This Code</h3>
          <p className="text-on-surface-variant text-sm mb-4 leading-relaxed">
            <strong>Type:</strong> {CODE_TYPE_LABELS[ct] ?? result.code_type}<br />
            <strong>Code:</strong> <code className="font-mono">{result.code}</code>
          </p>
          {result.source && (
            <p className="text-xs text-on-surface-variant leading-relaxed">
              Data sourced from <strong>{result.source}</strong> — an authoritative regulatory database updated annually.
            </p>
          )}
        </div>
        <Link
          to="/indiana-resources"
          className="mt-6 flex items-center justify-between group p-4 bg-white rounded-xl border border-outline-variant/20 hover:border-primary transition-all"
        >
          <span className="font-headline font-bold text-sm text-primary">Indiana Resources</span>
          <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">arrow_forward</span>
        </Link>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

/** Code lookup UI nested under Indiana Resources (no sidebar). */
export default function CodeLookupContent() {
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
  const [selectedType, setSelectedType] = useState<CodeType | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<CodeLookupResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleLookup() {
    const trimmed = query.trim()
    if (!trimmed) return

    const codeType = selectedType ?? detectCodeType(trimmed)
    if (!codeType) {
      setError('Could not auto-detect code type. Please select ICD-10, CPT, CARC, RARC, HCPCS, or NPI.')
      return
    }

    setIsLoading(true)
    setError(null)
    setResult(null)

    try {
      const params = new URLSearchParams({ code: trimmed, type: codeType })
      const res = await fetch(`/api/v1/codes/lookup?${params}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail ?? `Server error ${res.status}`)
      }
      const data: CodeLookupResult = await res.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lookup failed. Is the backend running?')
    } finally {
      setIsLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') handleLookup()
  }

  function handleCategoryClick(type: CodeType) {
    setSelectedType(prev => (prev === type ? null : type))
    setResult(null)
    setError(null)
  }

  const detectedType = query.trim() ? detectCodeType(query.trim()) : null
  const activeType = selectedType ?? detectedType

  return (
    <div className="max-w-6xl mx-auto bg-surface pb-8">
      <nav className="mb-8 flex items-center gap-2 text-on-surface-variant font-medium text-[10px] uppercase tracking-widest">
        <Link to="/indiana-resources" className="hover:text-primary transition-colors">
          Indiana Resources
        </Link>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <span className="text-primary font-bold">Code &amp; Term Lookup</span>
      </nav>

      {/* Header + Search */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 mb-10">
        <div className="lg:col-span-7">
          <h1 className="text-4xl md:text-5xl font-extrabold font-headline text-primary tracking-tight mb-4">
            Code &amp; Term Lookup
          </h1>
          <p className="text-lg text-on-surface-variant leading-relaxed max-w-2xl">
            Look up any ICD-10, CPT, HCPCS, CARC, RARC, or NPI code. Results are fetched live from authoritative CMS and regulatory sources.
          </p>
        </div>
        <div className="lg:col-span-5 flex items-end">
          <div className="w-full bg-surface-container-lowest p-1 rounded-full shadow-lg border border-outline-variant/10 flex items-center">
            <span className="material-symbols-outlined ml-4 text-outline">search</span>
            <input
              value={query}
              onChange={e => { setQuery(e.target.value); setResult(null); setError(null) }}
              onKeyDown={handleKeyDown}
              className="flex-1 bg-transparent border-none focus:ring-0 text-sm px-4 py-3 h-14"
              placeholder="e.g. M54.5 · CPT 99213 · CARC CO-50 · NPI 1234567890"
              type="text"
            />
            <button
              type="button"
              onClick={handleLookup}
              disabled={isLoading || !query.trim()}
              className="bg-primary text-on-primary px-6 md:px-8 py-3 rounded-full font-headline font-bold text-sm tracking-wide mr-1 shadow-md hover:brightness-110 transition-all disabled:opacity-50"
            >
              {isLoading ? 'LOOKING…' : 'IDENTIFY'}
            </button>
          </div>
        </div>
      </div>

      {/* Auto-detected type indicator */}
      {activeType && query.trim() && (
        <div className="mb-6 flex items-center gap-2">
          <span className="text-xs text-on-surface-variant">
            {selectedType ? 'Type locked:' : 'Auto-detected:'}
          </span>
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${CODE_TYPE_COLORS[activeType]}`}>
            {CODE_TYPE_LABELS[activeType]}
          </span>
          {selectedType && (
            <button
              type="button"
              onClick={() => setSelectedType(null)}
              className="text-xs text-on-surface-variant hover:text-error underline"
            >
              clear
            </button>
          )}
        </div>
      )}

      {/* Category filter pills */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
        {CATEGORIES.map(({ icon, title, subtitle, type }) => {
          const active = activeType === type || selectedType === type
          return (
            <button
              key={title}
              type="button"
              onClick={() => handleCategoryClick(type)}
              className={`group relative overflow-hidden p-6 rounded-xl text-left transition-all duration-300
                ${active
                  ? 'bg-primary text-on-primary shadow-lg scale-[1.02]'
                  : 'bg-surface-container-low hover:bg-primary hover:text-on-primary'}`}
            >
              {active && (
                <div className="absolute top-3 right-3 bg-white/20 text-white text-[8px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest">
                  Active
                </div>
              )}
              <div className="flex flex-col gap-4">
                <span className={`material-symbols-outlined text-3xl transition-colors
                  ${active ? 'text-on-primary' : 'text-primary group-hover:text-on-primary'}`}>
                  {icon}
                </span>
                <div>
                  <h3 className={`font-headline font-bold text-lg transition-colors
                    ${active ? 'text-on-primary' : 'text-primary group-hover:text-on-primary'}`}>
                    {title}
                  </h3>
                  <p className={`text-xs font-medium transition-colors
                    ${active ? 'text-on-primary/70' : 'text-on-secondary-container group-hover:text-on-primary/70'}`}>
                    {subtitle}
                  </p>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Loading spinner */}
      {isLoading && (
        <div className="flex items-center justify-center py-16 gap-3">
          <span className="material-symbols-outlined text-primary animate-spin text-3xl">progress_activity</span>
          <span className="text-on-surface-variant font-medium">Looking up code…</span>
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div className="mb-8 flex items-start gap-3 p-5 bg-error-container rounded-xl border border-error/20">
          <span className="material-symbols-outlined text-error shrink-0">error</span>
          <p className="text-sm text-on-error-container font-medium">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && !isLoading && (
        <div className="mb-12">
          <ResultCard result={result} onDraftAppeal={() => navigate('/appeal-drafting')} />
        </div>
      )}

      {/* Placeholder when no result yet */}
      {!result && !isLoading && !error && (
        <div className="mb-12 bg-surface-container-lowest rounded-xl p-8 border border-outline-variant/10 flex items-center gap-6">
          <div className="bg-secondary-container w-14 h-14 rounded-full flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-primary text-2xl">manage_search</span>
          </div>
          <div>
            <p className="font-bold text-on-surface mb-1">Enter a code to get started</p>
            <p className="text-sm text-on-surface-variant">
              Examples: <button type="button" onClick={() => { setQuery('CO-50'); setSelectedType('carc') }} className="text-primary underline">CARC CO-50</button>
              {' · '}
              <button type="button" onClick={() => { setQuery('M54.5'); setSelectedType('icd10') }} className="text-primary underline">ICD-10 M54.5</button>
              {' · '}
              <button type="button" onClick={() => { setQuery('62323'); setSelectedType('cpt') }} className="text-primary underline">CPT 62323</button>
            </p>
          </div>
        </div>
      )}

      {/* Terminology Glossary */}
      <section className="mt-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-3xl font-headline font-bold text-primary tracking-tight">Terminology Glossary</h2>
            <p className="text-sm text-on-surface-variant">Essential medical-legal vocabulary for successful appeals.</p>
          </div>
        </div>
        <div className="flex gap-6 overflow-x-auto no-scrollbar pb-8">
          {glossaryTerms.map(({ category, term, def }) => (
            <div key={term} className="min-w-[320px] bg-surface-container-lowest p-6 rounded-xl shadow-sm border border-outline-variant/10">
              <span className="text-[10px] font-bold text-primary uppercase tracking-widest mb-2 block">{category}</span>
              <h4 className="font-headline font-extrabold text-xl text-on-surface mb-3">{term}</h4>
              <p className="text-sm text-on-surface-variant leading-relaxed">{def}</p>
            </div>
          ))}
        </div>
      </section>

      <p className="mt-12 text-xs text-on-surface-variant border-t border-outline-variant/30 pt-8 leading-relaxed">
        Disclaimer: Resolvly is an advocacy tool and does not provide legal advice or medical diagnosis. All code lookup data is fetched live from authoritative CMS and regulatory sources for informational purposes only.
      </p>
    </div>
  )
}
