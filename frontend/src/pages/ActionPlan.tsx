import { useState } from 'react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

const steps = [
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

export default function ActionPlan() {
  const [openStep, setOpenStep] = useState<number | null>(null)
  const [reminders, setReminders] = useState({ weekly: true, urgent: true, regulatory: false })

  return (
    <div className="bg-background text-on-surface antialiased min-h-screen flex flex-col">
      <Navbar />

      <main className="pt-24 pb-12 px-8 max-w-7xl mx-auto flex-grow">
        {/* Header */}
        <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-tertiary-fixed text-on-tertiary-fixed text-[10px] uppercase tracking-widest font-bold">
              <span className="material-symbols-outlined text-sm">priority_high</span>
              Time-Sensitive
            </div>
            <h1 className="text-5xl font-extrabold font-headline tracking-tighter text-primary">Action Plan &amp; Deadlines</h1>
            <p className="text-on-surface-variant max-w-2xl leading-relaxed">
              Your comprehensive recovery roadmap for Case #ID-440291. We have identified specific regulatory paths based on Indiana state law and ERISA guidelines.
            </p>
          </div>
          <div className="glass-card p-6 rounded-xl border border-outline-variant/15 flex items-center gap-6">
            <div className="relative w-20 h-20">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <path className="text-surface-container-high" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray="100, 100" strokeWidth="3" />
                <path className="text-primary" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeDasharray="84, 100" strokeLinecap="round" strokeWidth="3" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center font-headline font-bold text-primary">84%</div>
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
              <div className="rounded-xl border border-outline-variant/15 bg-surface-container-lowest p-8 shadow-sm dark:border-slate-600/35">
                <div className="mb-6 flex items-center justify-between">
                  <h3 className="font-headline text-lg font-bold text-on-surface">Bill Breakdown</h3>
                  <span className="material-symbols-outlined text-outline">account_balance_wallet</span>
                </div>
                <div className="space-y-4">
                  {[
                    { label: 'Billed Amount', value: '$12,450.00', cls: '' },
                    { label: 'Allowed Amount', value: '$1,200.00', cls: 'text-error' },
                  ].map(({ label, value, cls }) => (
                    <div key={label} className="flex justify-between items-center py-2 border-b border-surface-container">
                      <span className="text-on-surface-variant text-sm">{label}</span>
                      <span className={`font-headline font-bold ${cls}`}>{value}</span>
                    </div>
                  ))}
                  <div className="flex justify-between items-center pt-4">
                    <span className="text-primary font-bold">Disputed Gap</span>
                    <span className="text-2xl font-extrabold text-primary">$11,250.00</span>
                  </div>
                </div>
              </div>

              <div className="relative overflow-hidden rounded-xl border border-outline-variant/15 bg-secondary-container p-8 dark:border-slate-600/40 dark:bg-slate-800/90">
                <div className="relative z-10">
                  <h3 className="mb-4 font-headline text-lg font-bold text-on-secondary-fixed-variant dark:text-slate-200">
                    Regulatory Routing
                  </h3>
                  <div className="space-y-4">
                    <div className="rounded-lg bg-white/50 p-4 ring-1 ring-black/5 dark:!bg-slate-950/90 dark:ring-slate-600/50">
                      <div className="mb-1 flex items-center gap-2">
                        <span className="material-symbols-outlined text-sm text-on-secondary-fixed dark:text-slate-300">gavel</span>
                        <span className="text-xs font-bold uppercase tracking-widest text-on-secondary-fixed dark:text-slate-300">
                          Entity Determination
                        </span>
                      </div>
                      <div className="mb-1 text-xl font-extrabold text-on-secondary-fixed dark:text-white">IDOI (Indiana)</div>
                      <p className="text-sm leading-tight text-on-secondary-fixed-variant dark:text-slate-400">
                        This plan is fully insured and subject to IDOI IC 27-8-28 oversight.
                      </p>
                    </div>
                    <div className="pointer-events-none opacity-40 grayscale dark:opacity-100 dark:grayscale-0">
                      <div className="text-xs font-bold uppercase tracking-widest text-on-secondary-fixed dark:text-slate-500">
                        Alternative: ERISA
                      </div>
                      <div className="text-lg font-bold text-on-secondary-fixed dark:text-slate-400">US Dept of Labor</div>
                    </div>
                  </div>
                </div>
                <span className="material-symbols-outlined absolute -bottom-8 -right-8 text-9xl text-on-secondary-container/10 dark:text-slate-600/40">
                  policy
                </span>
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
            <div className="rounded-xl border border-outline-variant/15 bg-surface-container-lowest p-8 shadow-sm dark:border-slate-600/35">
              <h3 className="mb-6 font-headline text-xl font-bold text-on-surface">Critical Deadlines</h3>
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-12 h-14 bg-error-container rounded-lg flex flex-col items-center justify-center">
                    <span className="text-[10px] font-bold text-on-error-container uppercase">Nov</span>
                    <span className="text-xl font-extrabold text-on-error-container leading-none">12</span>
                  </div>
                  <div className="flex-grow">
                    <div className="text-sm font-bold text-primary">Internal Appeal Window</div>
                    <div className="text-xs text-on-surface-variant">180 days from EOB receipt</div>
                    <button className="mt-2 text-primary text-[10px] font-bold uppercase tracking-widest flex items-center gap-1 hover:text-primary-container">
                      <span className="material-symbols-outlined text-sm">calendar_add_on</span> Add to Calendar
                    </button>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-12 h-14 bg-surface-container rounded-lg flex flex-col items-center justify-center opacity-60">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase">Jan</span>
                    <span className="text-xl font-extrabold text-on-surface-variant leading-none">28</span>
                  </div>
                  <div className="flex-grow">
                    <div className="text-sm font-bold text-on-surface-variant">IDOI Filing Deadline</div>
                    <div className="text-xs text-on-surface-variant">External Review window</div>
                    <button className="mt-2 text-primary text-[10px] font-bold uppercase tracking-widest flex items-center gap-1">
                      <span className="material-symbols-outlined text-sm">calendar_today</span> .ics Export
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Reminders: light = brand primary; dark = slate only (!) so theme token primary (light blue) never paints the card */}
            <div className="rounded-xl bg-primary p-8 text-on-primary shadow-lg ring-1 ring-black/10 dark:!bg-slate-950 dark:!text-slate-100 dark:ring-sky-500/25">
              <div className="mb-4 flex items-center gap-3">
                <span className="material-symbols-outlined text-on-primary dark:!text-sky-400">mail</span>
                <h3 className="font-headline text-lg font-bold text-on-primary dark:!text-slate-50">Reminders</h3>
              </div>
              <p className="mb-6 text-sm text-on-primary/90 dark:!text-slate-400">
                Stay ahead of deadlines. We will notify you 7 days before any critical window closes.
              </p>
              <div className="space-y-3">
                {[
                  { key: 'weekly', label: 'Weekly Case Summary' },
                  { key: 'urgent', label: 'Urgent Deadline Alerts' },
                  { key: 'regulatory', label: 'Regulatory Policy Updates' },
                ].map(({ key, label }) => (
                  <label key={key} className="group flex cursor-pointer items-center gap-3">
                    <input
                      checked={reminders[key as keyof typeof reminders]}
                      onChange={() => setReminders(r => ({ ...r, [key]: !r[key as keyof typeof reminders] }))}
                      className="rounded border border-white/20 bg-primary-container focus:ring-0 dark:border-slate-600 dark:!bg-slate-800 accent-sky-500 dark:accent-sky-400"
                      type="checkbox"
                    />
                    <span className="text-sm font-medium text-on-primary transition-colors group-hover:text-white dark:!text-slate-200 dark:group-hover:!text-sky-300">
                      {label}
                    </span>
                  </label>
                ))}
              </div>
              <button
                type="button"
                className="mt-6 w-full rounded-lg bg-white py-3 text-sm font-bold text-primary shadow-lg transition-colors hover:bg-slate-50 dark:border dark:!border-slate-600 dark:!bg-slate-800 dark:!text-slate-100 dark:shadow-none dark:hover:!bg-slate-700"
              >
                Update Preferences
              </button>
            </div>

            {/* Case Manager */}
            <div className="rounded-xl border border-outline-variant/15 bg-surface-container-high p-6 dark:border-slate-600/35">
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
                "Based on your denial code (CO-197), I recommend prioritizing the medical record collection immediately."
              </p>
              <button
                type="button"
                className="w-full rounded border border-primary py-2 text-xs font-bold uppercase tracking-widest text-primary transition-all hover:bg-primary hover:text-on-primary dark:hover:text-white"
              >
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
