import { useState, useEffect, useMemo } from 'react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { loadAnalysisBundle } from '../lib/sessionKeys'
import { postAppealLetter, postExportPdf } from '../lib/api'

const tabs = ['Appeal Letter (Draft)', 'Message to Provider', 'Message to Insurer']

const STATIC_DRAFT = `[DATE]
Indiana Department of Insurance
311 West Washington Street
Indianapolis, IN 46204

RE: Appeal of Coverage Denial for Patient [PATIENT_NAME]
Member ID: [MEMBER_ID] | Case Ref: #IN-99283-X

To the Consumer Services Division,

I am writing to formally appeal the denial of coverage issued by [CARRIER_NAME] regarding medical services provided on [SERVICE_DATE]. Under Indiana Code § 27-8-28, I am exercising my right to a formal review of this determination.

The denial was based on the assertion that the treatment was "not medically necessary." However, the following Indiana-specific regulatory clinical criteria were not properly applied in this assessment...

[AI NOTE: Insert specific clinical justification here. The uploaded EOB indicates code 99214 was contested. Resolvly suggests referencing IN-Admin-Code Title 760 for peer-review standards.]

Attached you will find the provider's certification and the itemized denial statement. I request a response within the 30-day statutory period required for standard appeals.

Sincerely,

[USER_SIGNATURE]`

const gaps = [
  { icon: 'help_outline', iconClass: 'text-tertiary-container', title: 'Ambiguous Procedure Codes', desc: 'Code 99284 was listed without a primary diagnosis link. Verify with provider.' },
  { icon: 'event_busy', iconClass: 'text-error', title: 'Missing Date of Service', desc: 'Page 3 of the PDF upload was blurry; the discharge date was estimated.' },
  { icon: 'info', iconClass: 'text-primary', title: 'Provider Credential Gap', desc: 'The NPI for the referring physician is missing from the appeal header.' },
]

const actionItems = [
  { label: 'Finalize Member ID in header', done: false },
  { label: 'Download PDF Draft', done: true },
  { label: 'Attach Physician Statement', done: false },
  { label: 'Mail via Certified Delivery', done: false },
]

export default function AppealDrafting() {
  const [activeTab, setActiveTab] = useState(0)
  const [items, setItems] = useState(actionItems)
  const bundle = useMemo(() => loadAnalysisBundle(), [])
  const [drafts, setDrafts] = useState<[string, string, string]>([STATIC_DRAFT, STATIC_DRAFT, STATIC_DRAFT])

  useEffect(() => {
    if (!bundle) return
    postAppealLetter(bundle.claim_object, bundle.analysis, bundle.enrichment, {})
      .then(r => {
        setDrafts([
          (typeof r.appeal_letter === 'string' && r.appeal_letter) ? r.appeal_letter : STATIC_DRAFT,
          (typeof r.provider_message === 'string' && r.provider_message) ? r.provider_message : STATIC_DRAFT,
          (typeof r.insurer_message === 'string' && r.insurer_message) ? r.insurer_message : STATIC_DRAFT,
        ])
      })
      .catch(() => {})
  }, [bundle])

  async function exportPdf() {
    const content = drafts[activeTab]
    try {
      const blob = await postExportPdf({ content, format: 'appeal_letter', title: 'Appeal draft' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 'appeal-draft.pdf'
      a.click()
      URL.revokeObjectURL(a.href)
    } catch {
      /* silent */
    }
  }

  function downloadTxt() {
    const blob = new Blob([drafts[activeTab]], { type: 'text/plain;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'appeal-draft.txt'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function copyDraft() {
    void navigator.clipboard.writeText(drafts[activeTab])
  }

  return (
    <div className="bg-background text-on-background selection:bg-secondary-container min-h-screen flex flex-col">
      <Navbar />

      <main className="pt-24 pb-12">
        {/* Warning Banner */}
        <div className="mx-8 mb-8">
          <div className="bg-tertiary-fixed text-on-tertiary-fixed p-4 rounded-xl flex items-center gap-3 shadow-sm">
            <span className="material-symbols-outlined text-on-tertiary-fixed-variant">warning</span>
            <span className="font-medium">
              Draft only—edit and verify. This content is AI-generated based on provided documents and Indiana regulations. Professional review is required.
            </span>
          </div>
        </div>

        <div className="editorial-margin pr-8">
          <header className="mb-12">
            <h1 className="text-4xl md:text-5xl font-extrabold font-headline text-primary tracking-tight mb-2">
              Appeal Drafting Room
            </h1>
            <p className="text-on-surface-variant max-w-2xl leading-relaxed">
              Prepare and refine your communication strategy for the Indiana Department of Insurance (IDOI) and private carriers.
            </p>
          </header>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Main Editor */}
            <div className="lg:col-span-8 space-y-6">
              {/* Tabs */}
              <div className="bg-surface-container-low rounded-xl p-1 flex gap-1">
                {tabs.map((tab, i) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(i)}
                    className={`flex-1 py-3 px-4 rounded-lg text-sm font-semibold transition-all ${activeTab === i ? 'bg-surface-container-lowest text-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-container-high'}`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {/* Editor Canvas */}
              <div className="bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/10 overflow-hidden">
                {/* Toolbar */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-surface-container">
                  <div className="flex items-center gap-4">
                    <span className="text-xs font-bold uppercase tracking-widest text-outline">v1.2 Draft</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={() => copyDraft()} className="p-2 hover:bg-surface-container rounded-lg text-primary transition-colors" title="Copy">
                      <span className="material-symbols-outlined">content_copy</span>
                    </button>
                    <button type="button" onClick={() => downloadTxt()} className="flex items-center gap-2 px-3 py-2 hover:bg-surface-container rounded-lg text-primary transition-colors text-sm font-medium">
                      <span className="material-symbols-outlined text-[20px]">download</span> .txt
                    </button>
                    <button type="button" onClick={() => void exportPdf()} className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg transition-all hover:opacity-90 text-sm font-medium">
                      <span className="material-symbols-outlined text-[20px]">picture_as_pdf</span> PDF Export
                    </button>
                  </div>
                </div>

                {/* Paper */}
                <div className="p-10 min-h-[600px] text-on-surface leading-loose"
                  style={{ background: 'linear-gradient(to bottom, transparent 31px, #f3f4f5 32px)', backgroundSize: '100% 32px' }}>
                  <div className="max-w-prose mx-auto bg-white p-8 shadow-sm">
                    <div className="whitespace-pre-wrap text-sm text-on-surface leading-relaxed">
                      {drafts[activeTab]}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Sidebar */}
            <div className="lg:col-span-4 space-y-8">
              {/* Assumptions & Gaps */}
              <section className="bg-surface-container-high p-6 rounded-xl">
                <div className="flex items-center gap-2 mb-4">
                  <span className="material-symbols-outlined text-primary">psychology</span>
                  <h3 className="font-headline font-bold text-lg text-primary">Assumptions &amp; Gaps</h3>
                </div>
                <ul className="space-y-4">
                  {gaps.map(({ icon, iconClass, title, desc }) => (
                    <li key={title} className="flex gap-3 items-start">
                      <span className={`material-symbols-outlined mt-0.5 text-[20px] ${iconClass}`}>{icon}</span>
                      <div>
                        <p className="text-sm font-semibold text-on-surface">{title}</p>
                        <p className="text-xs text-on-surface-variant">{desc}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>

              {/* Action Plan */}
              <section className="bg-surface-container-low p-6 rounded-xl">
                <h3 className="font-headline font-bold text-lg text-primary mb-4">Action Plan</h3>
                <div className="space-y-3">
                  {items.map((item, i) => (
                    <label key={item.label} className="flex items-center gap-3 p-3 bg-surface-container-lowest rounded-lg border border-transparent hover:border-outline-variant/30 cursor-pointer transition-all">
                      <input
                        className="rounded-sm text-primary focus:ring-primary h-4 w-4"
                        type="checkbox"
                        checked={item.done}
                        onChange={() => setItems(items.map((it, idx) => idx === i ? { ...it, done: !it.done } : it))}
                      />
                      <span className={`text-sm font-medium ${item.done ? 'line-through text-on-surface-variant' : ''}`}>{item.label}</span>
                    </label>
                  ))}
                </div>
              </section>

              {/* Indiana Resources */}
              <section className="bg-primary text-on-primary p-6 rounded-xl shadow-lg relative overflow-hidden">
                <div className="relative z-10">
                  <h3 className="font-headline font-bold text-lg mb-4">Indiana Resources</h3>
                  <div className="space-y-4 mb-6">
                    <div className="flex items-center gap-3">
                      <span className="material-symbols-outlined text-secondary-fixed">account_balance</span>
                      <span className="text-sm font-semibold">IDOI Consumer Division</span>
                    </div>
                    <div className="text-xs space-y-1 opacity-90 leading-relaxed">
                      <p>311 West Washington Street, Suite 300</p>
                      <p>Indianapolis, IN 46204-2787</p>
                      <p className="pt-2">Hotline: 1-800-622-4461</p>
                    </div>
                  </div>
                  <a href="#" className="inline-flex items-center justify-center w-full bg-on-primary text-primary px-4 py-3 rounded-lg font-bold text-sm hover:bg-secondary-container transition-colors">
                    Open IDOI Website
                    <span className="material-symbols-outlined ml-2 text-[18px]">open_in_new</span>
                  </a>
                </div>
                <div className="absolute -bottom-4 -right-4 opacity-10">
                  <span className="material-symbols-outlined text-[120px]">gavel</span>
                </div>
              </section>
            </div>
          </div>
        </div>
      </main>

      <Footer disclaimer="Disclaimer: Resolvly is an advocacy platform and does not provide legal advice. All drafting tools should be reviewed by an attorney or qualified patient advocate before submission to insurers or the State of Indiana." />
    </div>
  )
}
