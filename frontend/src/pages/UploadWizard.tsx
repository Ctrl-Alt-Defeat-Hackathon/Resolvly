import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

type DocType = 'denial' | 'eob' | 'bill'

interface UploadedDoc {
  name: string
  size: string
}

const DOC_SLOTS: { type: DocType; label: string; desc: string; icon: string; mockName: string }[] = [
  {
    type: 'denial',
    label: 'Denial Letter',
    desc: 'The letter from your insurer stating the denial reason and codes.',
    icon: 'cancel',
    mockName: 'Denial_Letter_2024.pdf',
  },
  {
    type: 'eob',
    label: 'Explanation of Benefits (EOB)',
    desc: 'Summary of costs and what your insurer paid vs. denied.',
    icon: 'receipt_long',
    mockName: 'EOB_Anthem_2024.pdf',
  },
  {
    type: 'bill',
    label: 'Medical Bill',
    desc: 'The itemized bill from your provider or hospital.',
    icon: 'local_hospital',
    mockName: 'Medical_Bill_2024.pdf',
  },
]

export default function UploadWizard() {
  const navigate = useNavigate()
  const [uploads, setUploads] = useState<Partial<Record<DocType, UploadedDoc>>>({})
  const [planType, setPlanType] = useState('')
  const [funding, setFunding] = useState('')
  const inputRefs = useRef<Partial<Record<DocType, HTMLInputElement | null>>>({})

  const allUploaded = DOC_SLOTS.every(s => !!uploads[s.type])
  const canAnalyze = allUploaded && !!planType

  function handleFile(type: DocType, files: FileList | null) {
    if (!files || files.length === 0) return
    const f = files[0]
    setUploads(u => ({ ...u, [type]: { name: f.name, size: `${(f.size / 1024 / 1024).toFixed(1)} MB` } }))
  }

  // Simulates a file selection for demo purposes
  function triggerUpload(type: DocType) {
    const slot = DOC_SLOTS.find(s => s.type === type)!
    setUploads(u => ({ ...u, [type]: { name: slot.mockName, size: '1.4 MB' } }))
  }

  function removeFile(type: DocType) {
    setUploads(u => {
      const next = { ...u }
      delete next[type]
      return next
    })
  }

  return (
    <div className="bg-background text-on-background font-body min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-grow pt-24 pb-12 px-6 md:px-12 lg:px-24">
        <div className="max-w-6xl mx-auto space-y-12">

          {/* Header */}
          <header className="max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 bg-secondary-container text-on-secondary-container px-3 py-1 rounded-full text-xs font-bold tracking-widest uppercase">
              <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>auto_fix</span>
              Multi-Doc Stitching Active
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold font-headline tracking-tight text-primary leading-tight">
              Upload &amp; Context Wizard
            </h1>
            <p className="text-lg text-on-surface-variant leading-relaxed font-medium">
              Our Indiana-specific engine requires specific policy context to frame your appeal. We analyze your denials through the lens of local regulatory frameworks.
            </p>
          </header>

          {/* Wizard Layout — LEFT: upload, RIGHT: policy intelligence */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">

            {/* LEFT: File Upload + CTA */}
            <section className="lg:col-span-7 space-y-6">

              {/* Document Slots */}
              <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-1 shadow-sm dark:border-slate-600/30">
                <div className="space-y-4 rounded-xl border-2 border-dashed border-outline-variant bg-surface/50 p-8 dark:border-slate-600/50 dark:bg-surface-container/90">
                  <div className="text-center mb-6">
                    <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-secondary-container text-primary dark:bg-primary/20">
                      <span className="material-symbols-outlined text-3xl">upload_file</span>
                    </div>
                    <h3 className="text-xl font-bold font-headline text-on-surface">Upload your documents</h3>
                    <p className="text-sm text-on-surface-variant mt-1">All three document types are required to begin analysis.</p>
                  </div>

                  {/* 3 doc type slots */}
                  <div className="space-y-3">
                    {DOC_SLOTS.map(slot => {
                      const uploaded = uploads[slot.type]
                      return (
                        <div
                          key={slot.type}
                          className={`flex items-center gap-4 rounded-xl border p-4 transition-all
                            ${uploaded
                              ? 'border-emerald-400/80 bg-emerald-50 dark:border-emerald-600/70 dark:bg-emerald-950/45'
                              : 'border-outline-variant/25 bg-surface-container-lowest hover:border-primary/35 dark:border-slate-600/50 dark:bg-surface-container-high dark:hover:border-primary/45'}`}
                        >
                          {/* Icon */}
                          <div
                            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg
                            ${uploaded ? 'bg-emerald-100 dark:bg-emerald-900/60' : 'bg-surface-container dark:bg-surface-container-highest'}`}
                          >
                            <span
                              className={`material-symbols-outlined text-xl
                              ${uploaded ? 'text-emerald-600 dark:text-emerald-400' : 'text-on-surface-variant'}`}
                            >
                              {uploaded ? 'check_circle' : slot.icon}
                            </span>
                          </div>

                          {/* Label + file name */}
                          <div className="min-w-0 flex-1">
                            <p
                              className={`text-sm font-bold ${uploaded ? 'text-emerald-900 dark:text-emerald-200' : 'text-on-surface'}`}
                            >
                              {slot.label}
                            </p>
                            {uploaded ? (
                              <p className="truncate text-xs text-emerald-700 dark:text-emerald-300/90">
                                {uploaded.name} · {uploaded.size}
                              </p>
                            ) : (
                              <p className="text-xs text-on-surface-variant">{slot.desc}</p>
                            )}
                          </div>

                          {/* Upload / Remove button */}
                          {uploaded ? (
                            <button
                              onClick={() => removeFile(slot.type)}
                              className="flex shrink-0 items-center gap-1 rounded-lg bg-emerald-100 px-3 py-1.5 text-xs font-bold text-emerald-800 transition-colors hover:bg-red-100 hover:text-red-600 dark:bg-emerald-900/50 dark:text-emerald-200 dark:hover:bg-red-950/60 dark:hover:text-red-300"
                            >
                              <span className="material-symbols-outlined text-sm">close</span>
                              Remove
                            </button>
                          ) : (
                            <>
                              <input
                                ref={el => { inputRefs.current[slot.type] = el }}
                                type="file"
                                accept=".pdf,.jpg,.png"
                                className="hidden"
                                onChange={e => handleFile(slot.type, e.target.files)}
                              />
                              <button
                                onClick={() => triggerUpload(slot.type)}
                                className="flex shrink-0 items-center gap-1 rounded-lg bg-surface-container-high px-4 py-1.5 text-xs font-bold text-primary transition-colors hover:bg-primary hover:text-on-primary dark:bg-slate-700/80 dark:hover:bg-primary dark:hover:text-on-primary"
                              >
                                <span className="material-symbols-outlined text-sm">upload</span>
                                Select
                              </button>
                            </>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* Stitching Progress (shown once any file is uploaded) */}
              {Object.keys(uploads).length > 0 && (
                <div className="space-y-4 rounded-xl bg-surface-container-low p-6 dark:bg-surface-container/80">
                  <div className="flex justify-between items-center">
                    <h4 className="text-xs font-bold tracking-widest text-primary uppercase">Stitching Progress</h4>
                    <span className="text-xs font-bold text-on-surface-variant">
                      {Object.keys(uploads).length} of 3 Documents Uploaded
                    </span>
                  </div>
                  <div className="space-y-3">
                    {DOC_SLOTS.filter(s => uploads[s.type]).map(slot => (
                      <div
                        key={slot.type}
                        className="flex items-center gap-4 rounded-lg border border-outline-variant/25 bg-surface-container-lowest p-3 dark:border-slate-600/40 dark:bg-surface-container-high"
                      >
                        <span className="material-symbols-outlined text-secondary">description</span>
                        <div className="flex-grow">
                          <div className="text-xs font-bold text-on-surface">{uploads[slot.type]!.name}</div>
                          <div className="h-1.5 w-full bg-surface-container rounded-full mt-1 overflow-hidden">
                            <div className="h-full bg-emerald-500 w-full transition-all" />
                          </div>
                        </div>
                        <span className="material-symbols-outlined text-emerald-500 text-sm">check_circle</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* CTA Button */}
              <div className="flex flex-col md:flex-row items-center gap-6 pt-2">
                <button
                  onClick={() => canAnalyze && navigate('/action-plan')}
                  disabled={!canAnalyze}
                  className={`flex w-full items-center justify-center gap-3 rounded-xl px-10 py-4 font-headline text-lg font-bold shadow-lg transition-all md:w-auto
                    ${canAnalyze
                      ? 'signature-cta cursor-pointer text-white hover:scale-[1.02] hover:shadow-xl'
                      : 'cursor-not-allowed bg-primary/25 text-white/55 dark:bg-primary/20 dark:text-white/40'}`}
                >
                  Begin Forensic Analysis
                  <span className="material-symbols-outlined">analytics</span>
                </button>
                <p className="text-xs text-on-surface-variant leading-tight">
                  {canAnalyze
                    ? <span className="font-semibold text-emerald-700 dark:text-emerald-400">✓ Ready — all documents uploaded and plan selected.</span>
                    : <>Upload all 3 documents and select a plan type to proceed.</>}
                </p>
              </div>
            </section>

            {/* RIGHT: Policy Intelligence */}
            <section className="lg:col-span-5 space-y-6">
              <div className="space-y-8 rounded-xl bg-surface-container-low p-8 dark:bg-surface-container/70">
                <div className="space-y-2">
                  <h2 className="text-xl font-bold font-headline text-primary">Policy Intelligence</h2>
                  <p className="text-sm text-on-surface-variant">Provide the foundational details of your coverage.</p>
                </div>

                {/* Plan Type */}
                <div className="space-y-4">
                  <label className="text-sm font-bold tracking-tight text-primary uppercase flex items-center gap-2">
                    <span className="w-1 h-4 bg-primary rounded-full" />
                    What kind of plan is this?
                  </label>
                  <div className="grid grid-cols-1 gap-3">
                    {[
                      { value: 'employer', label: 'Employer', desc: 'Coverage provided via your workplace.' },
                      { value: 'individual', label: 'Individual', desc: 'Marketplace or private purchase.' },
                      { value: 'medicaid', label: 'Medicaid', desc: 'State-sponsored healthcare assistance.' },
                    ].map(({ value, label, desc }) => (
                      <label
                        key={value}
                        className={`flex cursor-pointer items-center gap-4 rounded-lg border bg-surface-container-lowest p-4 transition-all dark:bg-surface-container-lowest/80
                          ${planType === value ? 'border-primary/50 bg-blue-50/60 dark:border-primary/45 dark:bg-primary/12' : 'border-transparent hover:border-primary/25 dark:hover:border-primary/35'}`}
                      >
                        <input
                          className="text-primary focus:ring-primary h-5 w-5 border-outline"
                          name="plan_type"
                          type="radio"
                          value={value}
                          checked={planType === value}
                          onChange={() => setPlanType(value)}
                        />
                        <div className="flex flex-col">
                          <span className="font-bold text-on-surface">{label}</span>
                          <span className="text-xs text-on-surface-variant">{desc}</span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Funding Structure */}
                <div className="space-y-4">
                  <label className="text-sm font-bold tracking-tight text-primary uppercase flex items-center gap-2">
                    <span className="w-1 h-4 bg-primary rounded-full" />
                    Funding Structure
                  </label>
                  <div className="grid grid-cols-1 gap-3">
                    {[
                      { value: 'erisa', label: 'Self-funded ERISA', desc: 'Governed by federal labor laws.' },
                      { value: 'insured', label: 'Fully Insured', desc: 'Subject to Indiana IDOI regulations.' },
                    ].map(({ value, label, desc }) => (
                      <label
                        key={value}
                        className={`flex cursor-pointer items-center gap-4 rounded-lg border bg-surface-container-lowest p-4 transition-all dark:bg-surface-container-lowest/80
                          ${funding === value ? 'border-primary/50 bg-blue-50/60 dark:border-primary/45 dark:bg-primary/12' : 'border-transparent hover:border-primary/25 dark:hover:border-primary/35'}`}
                      >
                        <input
                          className="text-primary focus:ring-primary h-5 w-5 border-outline"
                          name="funding"
                          type="radio"
                          value={value}
                          checked={funding === value}
                          onChange={() => setFunding(value)}
                        />
                        <div className="flex flex-col">
                          <span className="font-bold text-on-surface">{label}</span>
                          <span className="text-xs text-on-surface-variant">{desc}</span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Status indicator */}
                {planType && (
                  <div className="flex items-center gap-2 rounded-lg border border-emerald-300/80 bg-emerald-50 p-3 dark:border-emerald-700/60 dark:bg-emerald-950/40">
                    <span className="material-symbols-outlined text-sm text-emerald-600 dark:text-emerald-400">check_circle</span>
                    <span className="text-xs font-semibold text-emerald-800 dark:text-emerald-200">Plan type selected</span>
                  </div>
                )}
              </div>

              {/* Info cards */}
              <div className="space-y-3">
                {[
                  { icon: 'gavel', title: 'Legal Compliance', desc: 'Automatic cross-referencing with Indiana Code Title 27 for comprehensive appeal grounding.' },
                  { icon: 'security', title: 'Data Sovereignty', desc: 'All data is encrypted and stays within our secure Indiana portal; never used for training public models.' },
                  { icon: 'history_edu', title: 'Drafting Engine', desc: 'The Context Wizard determines the tone and statutory language required for your specific denial type.' },
                ].map(({ icon, title, desc }) => (
                  <div
                    key={title}
                    className="space-y-1 rounded-xl border border-outline-variant/15 bg-surface-container-lowest p-5 dark:border-slate-600/35 dark:bg-surface-container-high/60"
                  >
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-primary text-lg">{icon}</span>
                      <h5 className="font-bold text-on-surface text-sm">{title}</h5>
                    </div>
                    <p className="text-xs text-on-surface-variant leading-relaxed">{desc}</p>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </main>

      <Footer />

      {/* Mobile Bottom Nav */}
      <div className="fixed bottom-0 z-50 flex h-16 w-full items-center justify-around border-t border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-950 md:hidden">
        {[
          { icon: 'home', label: 'Home', active: false, to: '/' },
          { icon: 'upload_file', label: 'Wizard', active: true, to: '/upload-wizard' },
          { icon: 'gavel', label: 'Plan', active: false, to: '/action-plan' },
          { icon: 'account_circle', label: 'Profile', active: false, to: '' },
        ].map(({ icon, label, active }) => (
          <button key={label} className={`flex flex-col items-center gap-1 ${active ? 'text-primary' : 'text-slate-400 dark:text-slate-500'}`}>
            <span className="material-symbols-outlined text-xl"
              style={active ? { fontVariationSettings: "'FILL' 1" } : {}}>{icon}</span>
            <span className="text-[10px] font-bold uppercase tracking-tighter">{label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
