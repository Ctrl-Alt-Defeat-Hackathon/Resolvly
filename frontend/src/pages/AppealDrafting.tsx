import { useState } from 'react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import ThemeToggle from '../components/ThemeToggle'

const tabs = ['Appeal Letter (Draft)', 'Message to Provider', 'Message to Insurer']

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
                <div className="flex items-center justify-between border-b border-surface-container px-6 py-4 dark:border-slate-700/60">
                  <div className="flex items-center gap-4">
                    <span className="text-xs font-bold uppercase tracking-widest text-outline dark:text-slate-400">v1.2 Draft</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <ThemeToggle />
                    <button
                      type="button"
                      className="rounded-lg p-2 text-primary transition-colors hover:bg-surface-container dark:hover:bg-slate-800"
                      title="Copy"
                    >
                      <span className="material-symbols-outlined">content_copy</span>
                    </button>
                    <button
                      type="button"
                      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-surface-container dark:hover:bg-slate-800"
                    >
                      <span className="material-symbols-outlined text-[20px]">download</span> .txt
                    </button>
                    <button
                      type="button"
                      className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary transition-all hover:opacity-90"
                    >
                      <span className="material-symbols-outlined text-[20px]">picture_as_pdf</span> PDF Export
                    </button>
                  </div>
                </div>

                {/* Paper: explicit light/dark surfaces so body text-on-surface (light in dark theme) never sits on white */}
                <div
                  className="min-h-[600px] bg-slate-100 p-10 leading-loose [background-image:linear-gradient(to_bottom,transparent_31px,rgb(226_232_240)_32px)] [background-size:100%_32px] dark:bg-slate-950 dark:[background-image:linear-gradient(to_bottom,transparent_31px,rgb(51_65_85)_32px)]"
                >
                  <div className="mx-auto max-w-prose bg-white p-8 text-slate-900 shadow-sm dark:border dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
                    <p className="mb-6">
                      [DATE]<br />
                      Indiana Department of Insurance<br />
                      311 West Washington Street<br />
                      Indianapolis, IN 46204
                    </p>
                    <p className="mb-6 font-bold">
                      RE: Appeal of Coverage Denial for Patient [PATIENT_NAME]<br />
                      Member ID: [MEMBER_ID] | Case Ref: #IN-99283-X
                    </p>
                    <p className="mb-4">To the Consumer Services Division,</p>
                    <p className="mb-4">
                      I am writing to formally appeal the denial of coverage issued by [CARRIER_NAME] regarding medical services provided on [SERVICE_DATE]. Under Indiana Code § 27-8-28, I am exercising my right to a formal review of this determination.
                    </p>
                    <p className="mb-4">
                      The denial was based on the assertion that the treatment was "not medically necessary." However, the following Indiana-specific regulatory clinical criteria were not properly applied in this assessment...
                    </p>
                    <div className="my-8 border-l-4 border-primary bg-slate-100 p-4 italic text-slate-700 dark:bg-slate-800/90 dark:text-slate-300">
                      [AI NOTE: Insert specific clinical justification here. The uploaded EOB indicates code 99214 was contested. Resolvly suggests referencing IN-Admin-Code Title 760 for peer-review standards.]
                    </div>
                    <p className="mb-4">
                      Attached you will find the provider's certification and the itemized denial statement. I request a response within the 30-day statutory period required for standard appeals.
                    </p>
                    <p>Sincerely,<br /><br /><br />[USER_SIGNATURE]</p>
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

              {/* Indiana Resources — dark: slate card so primary token (light blue) does not clash */}
              <section className="relative overflow-hidden rounded-xl bg-primary p-6 text-on-primary shadow-lg ring-1 ring-black/10 dark:!bg-slate-900 dark:!text-slate-100 dark:ring-sky-500/25">
                <div className="relative z-10">
                  <h3 className="mb-4 font-headline text-lg font-bold">Indiana Resources</h3>
                  <div className="mb-6 space-y-4">
                    <div className="flex items-center gap-3">
                      <span className="material-symbols-outlined text-secondary-fixed dark:!text-sky-400">account_balance</span>
                      <span className="text-sm font-semibold dark:!text-slate-100">IDOI Consumer Division</span>
                    </div>
                    <div className="space-y-1 text-xs leading-relaxed opacity-90 dark:!text-slate-400">
                      <p>311 West Washington Street, Suite 300</p>
                      <p>Indianapolis, IN 46204-2787</p>
                      <p className="pt-2">Hotline: 1-800-622-4461</p>
                    </div>
                  </div>
                  <a
                    href="#"
                    className="inline-flex w-full items-center justify-center rounded-lg bg-on-primary px-4 py-3 text-sm font-bold text-primary transition-colors hover:bg-secondary-container dark:!border dark:!border-slate-600 dark:!bg-slate-800 dark:!text-slate-100 dark:hover:!bg-slate-700"
                  >
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
