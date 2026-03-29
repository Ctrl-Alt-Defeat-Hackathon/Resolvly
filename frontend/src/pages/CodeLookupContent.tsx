import { Link, useNavigate } from 'react-router-dom'

const glossaryTerms = [
  { category: 'Legal Concept', term: 'Adjudication', def: 'The formal process by which an insurance carrier determines their financial responsibility for a specific claim.' },
  { category: 'Regulatory', term: 'Clean Claim', def: 'A claim that has no defect, impropriety, or lack of any required substantiating documentation, enabling immediate processing.' },
  { category: 'Standard', term: 'Medical Necessity', def: 'Health care services that a physician, exercising prudent clinical judgment, would provide to a patient for purposes of evaluation.' },
  { category: 'Policy', term: 'Provider Parity', def: 'The principle ensuring reimbursement rates for specialized services remain equitable across varying practitioner types.' },
]

const categories = [
  { icon: 'medical_information', title: 'ICD-10-CM', subtitle: 'Diagnostic Codes', active: false },
  { icon: 'clinical_notes', title: 'CPT/HCPCS', subtitle: 'Procedure Tracking', active: false },
  { icon: 'payments', title: 'CARC', subtitle: 'Claim Adjustments', active: true },
  { icon: 'receipt_long', title: 'RARC', subtitle: 'Remittance Advice', active: false },
]

/** Code lookup UI nested under Indiana Resources (no sidebar). */
export default function CodeLookupContent() {
  const navigate = useNavigate()

  return (
    <div className="max-w-6xl mx-auto bg-surface pb-8">
      <nav className="mb-8 flex items-center gap-2 text-on-surface-variant font-medium text-[10px] uppercase tracking-widest">
        <Link to="/indiana-resources" className="hover:text-primary transition-colors">
          Indiana Resources
        </Link>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <span className="text-primary font-bold">Code &amp; Term Lookup</span>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 mb-16">
        <div className="lg:col-span-7">
          <h1 className="text-4xl md:text-5xl font-extrabold font-headline text-primary tracking-tight mb-6">
            Code &amp; Term Lookup
          </h1>
          <p className="text-lg text-on-surface-variant leading-relaxed max-w-2xl">
            Navigate the labyrinth of insurance denials with precision. Our integrated lookup library translates complex regulatory jargon into actionable advocacy intelligence.
          </p>
        </div>
        <div className="lg:col-span-5 flex items-end">
          <div className="w-full bg-surface-container-lowest p-1 rounded-full shadow-lg border border-outline-variant/10 flex items-center">
            <span className="material-symbols-outlined ml-4 text-outline">search</span>
            <input className="flex-1 bg-transparent border-none focus:ring-0 text-sm px-4 py-3 h-14" placeholder="Search Code Intelligence (e.g., CPT 99213 or CARC CO-45)" type="text" />
            <button type="button" className="bg-primary text-on-primary px-6 md:px-8 py-3 rounded-full font-headline font-bold text-sm tracking-wide mr-1 shadow-md hover:brightness-110 transition-all">
              IDENTIFY
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
        {categories.map(({ icon, title, subtitle, active }) => (
          <button key={title} type="button" className={`group relative overflow-hidden p-6 rounded-xl text-left hover:bg-primary transition-all duration-300 ${active ? 'bg-surface-container-low border-2 border-primary-container' : 'bg-surface-container-low'}`}>
            {active && (
              <div className="absolute top-4 right-4 bg-tertiary-fixed text-on-tertiary-fixed text-[8px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest">Active</div>
            )}
            <div className="flex flex-col gap-4">
              <span className="material-symbols-outlined text-primary group-hover:text-on-primary transition-colors text-3xl">{icon}</span>
              <div>
                <h3 className="font-headline font-bold text-lg text-primary group-hover:text-on-primary">{title}</h3>
                <p className="text-xs text-on-secondary-container group-hover:text-on-primary/70 font-medium">{subtitle}</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
        <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col md:flex-row">
          <div className="p-8 flex-1">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-secondary-container text-on-secondary-container px-4 py-1.5 rounded-full font-headline font-bold text-lg">CO-97</div>
              <span className="text-on-surface-variant text-sm font-semibold uppercase tracking-widest">Claim Adjustment Reason Code</span>
            </div>
            <div className="space-y-6">
              <div>
                <h4 className="text-xs font-bold text-primary uppercase tracking-widest mb-1">Meaning</h4>
                <p className="text-on-surface font-semibold text-lg">The benefit for this service is included in the payment/allowance for another service/procedure that has already been adjudicated.</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-surface-container-low p-4 rounded-lg">
                  <h4 className="text-xs font-bold text-secondary uppercase tracking-widest mb-2 flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">record_voice_over</span> Plain English
                  </h4>
                  <p className="text-sm text-on-surface-variant leading-relaxed">
                    Your insurance company thinks they already paid for this. They believe this specific task was just a small part of a bigger procedure you&apos;ve already billed for.
                  </p>
                </div>
                <div className="bg-surface-container-low p-4 rounded-lg">
                  <h4 className="text-xs font-bold text-secondary uppercase tracking-widest mb-2 flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">psychology_alt</span> Typical Cause
                  </h4>
                  <p className="text-sm text-on-surface-variant leading-relaxed">
                    Commonly occurs with &quot;unbundling&quot;—where components of a surgery are billed separately instead of using a single comprehensive code.
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-primary p-8 md:w-72 flex flex-col justify-between">
            <div>
              <h4 className="text-xs font-bold text-primary-fixed uppercase tracking-widest mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">build</span> Common Fix
              </h4>
              <p className="text-on-primary text-sm leading-relaxed mb-6 font-medium">
                Review documentation for distinct modifier eligibility (e.g., Modifier -59). If services were truly separate sessions, provide timestamped proof or operative notes.
              </p>
            </div>
            <button type="button" onClick={() => navigate('/appeal-drafting')} className="w-full bg-white text-primary py-3 rounded-xl font-headline font-bold text-sm shadow-xl hover:scale-105 transition-transform">
              DRAFT APPEAL
            </button>
          </div>
        </div>

        <div className="bg-surface-container p-8 rounded-xl flex flex-col justify-between border-t-4 border-primary">
          <div>
            <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center mb-6 shadow-sm">
              <span className="material-symbols-outlined text-primary text-2xl">picture_as_pdf</span>
            </div>
            <h3 className="font-extrabold text-xl text-primary mb-2 leading-tight">Indiana Regulatory Standards</h3>
            <p className="text-on-surface-variant text-sm mb-6 leading-relaxed">
              Official handbook on clean claim standards and prompt payment regulations per Indiana Code § 27-8-5.7.
            </p>
          </div>
          <a href="#" className="flex items-center justify-between group p-4 bg-white rounded-xl border border-outline-variant/20 hover:border-primary transition-all">
            <span className="font-headline font-bold text-sm text-primary">Download PDF</span>
            <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">download</span>
          </a>
        </div>
      </div>

      <section className="mt-16">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-3xl font-headline font-bold text-primary tracking-tight">Terminology Glossary</h2>
            <p className="text-sm text-on-surface-variant">Essential medical-legal vocabulary for successful appeals.</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="p-2 rounded-full border border-outline-variant hover:bg-surface-container-high transition-colors">
              <span className="material-symbols-outlined">arrow_back</span>
            </button>
            <button type="button" className="p-2 rounded-full border border-outline-variant hover:bg-surface-container-high transition-colors">
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
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
        Disclaimer: Resolvly is an advocacy tool and does not provide legal advice or medical diagnosis. All code lookup data is provided for informational purposes only.
      </p>
    </div>
  )
}
