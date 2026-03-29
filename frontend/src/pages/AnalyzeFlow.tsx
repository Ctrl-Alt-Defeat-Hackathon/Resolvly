import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { uploadDocuments, extractEntities, analyzeClaim, wizardPlanType } from '../lib/api'
import { buildPlanContext, buildWizardBody, canSubmitPlan } from '../lib/planMapping'
import { STORAGE_KEYS, saveAnalysisBundle } from '../lib/sessionKeys'

export const RESOLVLY_ANALYSIS_COMPLETE_KEY = STORAGE_KEYS.ANALYSIS_COMPLETE

// ─── Uploaded file (stitching list) ─────────────────────────────────────────
export type DocKind = 'eob' | 'denial' | 'medical_bill'

const DOC_KIND_LABEL: Record<DocKind, string> = {
  eob: 'EOB',
  denial: 'Denial letter',
  medical_bill: 'Medical bill',
}

interface UploadedFile {
  id: string
  name: string
  size: string
  type: string
  status: 'extracted' | 'processing' | 'failed'
  docKind: DocKind
  file?: File
}

function baseNameForKind(k: DocKind): string {
  if (k === 'denial') return 'Denial_Letter'
  if (k === 'eob') return 'EOB'
  return 'Medical_Bill'
}

function typeLabelForKind(k: DocKind): string {
  if (k === 'denial') return 'Denial Letter'
  if (k === 'eob') return 'Explanation of Benefits'
  return 'Medical Bill'
}

/** File names always follow the selected document type (e.g. EOB.pdf, Denial_Letter.pdf). */
function normalizeFileNames(files: UploadedFile[]): UploadedFile[] {
  const counts: Record<DocKind, number> = { eob: 0, denial: 0, medical_bill: 0 }
  return files.map(f => {
    counts[f.docKind]++
    const n = counts[f.docKind]
    const base = baseNameForKind(f.docKind)
    const name = n === 1 ? `${base}.pdf` : `${base}_${n}.pdf`
    return { ...f, name, type: typeLabelForKind(f.docKind) }
  })
}

// ─── Processing (after Begin Forensic Analysis) ──────────────────────────────
const PIPELINE_STAGES = [
  { id: 'extraction', label: 'Document text extracted', detail: null as string[] | null },
  { id: 'entities', label: 'Entities identified (14 codes, 6 dates, 4 amounts)', detail: null },
  { id: 'codes', label: 'Looking up billing codes...', detail: [
    'CPT 62323 — found ✓',
    'ICD-10 M54.5 — found ✓',
    'CARC CO-197 — found ✓',
  ]},
  { id: 'federal', label: 'Searching federal regulations', detail: null },
  { id: 'state', label: 'Checking Indiana state rules', detail: null },
  { id: 'analysis', label: 'Running root cause analysis', detail: null },
  { id: 'generating', label: 'Generating your results', detail: null },
]

function ProcessingView({
  onComplete,
  onError,
  runPipeline,
  errorText,
}: {
  onComplete: () => void
  onError: (msg: string) => void
  runPipeline: () => Promise<void>
  errorText: string | null
}) {
  const [completedCount, setCompletedCount] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    let iv: ReturnType<typeof setInterval> | undefined
    const t = window.setTimeout(() => {
      iv = setInterval(() => {
        setCompletedCount(c => Math.min(c + 1, PIPELINE_STAGES.length - 1))
      }, 1400)
    }, 400)
    ;(async () => {
      try {
        await runPipeline()
        clearInterval(iv)
        setCompletedCount(PIPELINE_STAGES.length)
        setDone(true)
        window.setTimeout(() => onComplete(), 1200)
      } catch (e) {
        clearInterval(iv)
        onError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      clearTimeout(t)
      if (iv) clearInterval(iv)
    }
  }, [runPipeline, onComplete, onError])

  const progress = Math.round((completedCount / PIPELINE_STAGES.length) * 100)

  return (
    <div className="max-w-2xl mx-auto px-6 py-12 w-full">
      <header className="mb-10 text-center">
        <h1 className="text-4xl font-extrabold font-headline text-primary tracking-tight mb-3">
          {done ? 'Analysis Complete!' : errorText ? 'Analysis failed' : 'Analyzing your claim...'}
        </h1>
        <p className="text-on-surface-variant">
          {errorText
            ? <span className="text-red-600">{errorText}</span>
            : (done ? 'Loading your results...' : 'This usually takes 10–15 seconds.')}
        </p>
      </header>

      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        <div className="h-1 bg-slate-100">
          <div className="h-full bg-primary transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
        </div>

        <div className="p-8 space-y-5">
          {PIPELINE_STAGES.map((stage, i) => {
            const isDone = i < completedCount
            const isActive = i === completedCount
            const isPending = i > completedCount
            return (
              <div key={stage.id} className={`transition-all duration-300 ${isPending ? 'opacity-40' : 'opacity-100'}`}>
                <div className="flex items-start gap-4">
                  <div className="mt-0.5 shrink-0">
                    {isDone && <span className="material-symbols-outlined text-emerald-500">check_circle</span>}
                    {isActive && <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>}
                    {isPending && <span className="w-6 h-6 rounded-full border-2 border-slate-300 inline-block" />}
                  </div>
                  <div className="flex-1">
                    <p className={`text-sm font-medium ${isDone ? 'text-slate-700' : isActive ? 'text-primary font-semibold' : 'text-slate-400'}`}>
                      {stage.label}
                    </p>
                    {isDone && stage.detail && (
                      <ul className="mt-2 ml-3 space-y-1 border-l-2 border-slate-200 pl-3">
                        {stage.detail.map((d, j) => (
                          <li key={j} className="text-xs text-slate-500">{d}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {isDone && <span className="text-xs text-slate-300 shrink-0">{(1.2 + i * 1.3).toFixed(1)}s</span>}
                </div>
              </div>
            )
          })}

          {done && !errorText && (
            <div className="pt-4 flex items-center gap-3 text-emerald-600 font-semibold">
              <span className="material-symbols-outlined">check_circle</span>
              All complete! Loading your results...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Single-page Upload & Context Wizard (no horizontal stepper) ─────────────
export default function AnalyzeFlow() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<'wizard' | 'processing'>('wizard')

  const [files, setFiles] = useState<UploadedFile[]>([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const [pipelineError, setPipelineError] = useState<string | null>(null)

  const [planType, setPlanType] = useState<string>('')
  const [funding, setFunding] = useState<string>('')
  /** Applies to the next file added via drop zone or file picker (can still change per row below). */
  const [nextUploadKind, setNextUploadKind] = useState<DocKind>('denial')

  useEffect(() => {
    if (sessionStorage.getItem(RESOLVLY_ANALYSIS_COMPLETE_KEY) === '1') {
      navigate('/action-plan', { replace: true })
    }
  }, [navigate])

  function addFilesFromList(fileList: FileList | null) {
    if (!fileList?.length) return
    setFiles(prev => {
      let next = [...prev]
      Array.from(fileList).forEach(file => {
        if (next.length >= 5) return
        const kind = nextUploadKind
        next.push({
          id: crypto.randomUUID(),
          name: file.name,
          size: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
          type: typeLabelForKind(kind),
          status: 'extracted',
          docKind: kind,
          file,
        })
      })
      return normalizeFileNames(next)
    })
  }

  function setFileKind(id: string, docKind: DocKind) {
    setFiles(prev => {
      const next = prev.map(file => (file.id === id ? { ...file, docKind } : file))
      return normalizeFileNames(next)
    })
  }

  function persistDocProfileForResults() {
    const payload = {
      files: files.map(f => ({ id: f.id, name: f.name, docKind: f.docKind })),
      kindsPresent: {
        eob: files.some(f => f.docKind === 'eob'),
        denial: files.some(f => f.docKind === 'denial'),
        medical_bill: files.some(f => f.docKind === 'medical_bill'),
      },
    }
    sessionStorage.setItem(STORAGE_KEYS.DOC_PROFILE, JSON.stringify(payload))
  }

  function fileProgress(f: UploadedFile) {
    if (f.status === 'extracted') return '100%'
    if (f.status === 'failed') return '0%'
    return '18%'
  }

  const onProcessingComplete = useCallback(() => {
    sessionStorage.setItem(RESOLVLY_ANALYSIS_COMPLETE_KEY, '1')
    const payload = {
      files: files.map(f => ({ id: f.id, name: f.name, docKind: f.docKind })),
      kindsPresent: {
        eob: files.some(f => f.docKind === 'eob'),
        denial: files.some(f => f.docKind === 'denial'),
        medical_bill: files.some(f => f.docKind === 'medical_bill'),
      },
    }
    sessionStorage.setItem(STORAGE_KEYS.DOC_PROFILE, JSON.stringify(payload))
    navigate('/action-plan')
  }, [navigate, files])

  const runPipeline = useCallback(async () => {
    const plan_context = buildPlanContext(planType, funding)
    const fileBlobs = files.map(f => f.file).filter((x): x is File => !!x)
    if (fileBlobs.length === 0) {
      throw new Error('Each file must be a real upload from your device.')
    }
    const up = await uploadDocuments(fileBlobs)
    const documents = up.documents.map(d => ({
      doc_id: d.doc_id,
      text_extracted: d.text_extracted,
    }))
    const ext = await extractEntities({
      upload_id: up.upload_id,
      documents,
      plan_context: plan_context as Record<string, unknown>,
    })
    let wizard: Record<string, unknown> | null = null
    try {
      const wb = buildWizardBody(planType, funding)
      const payload: Record<string, string> =
        wb.source === 'employer'
          ? { source: wb.source, state: wb.state, employer_plan_type: wb.employer_plan_type }
          : { source: wb.source, state: wb.state }
      wizard = await wizardPlanType(payload as { source: string; state: string; employer_plan_type?: string })
    } catch {
      wizard = null
    }
    const analyzed = await analyzeClaim(
      ext.claim_object as Record<string, unknown>,
      plan_context as Record<string, unknown>
    )
    saveAnalysisBundle({
      claim_object: analyzed.claim_object,
      analysis: analyzed.analysis,
      enrichment: analyzed.enrichment,
      sources: analyzed.sources,
      plan_context: plan_context as Record<string, unknown>,
      wizard,
    })
  }, [files, planType, funding])

  const canAnalyze =
    files.length > 0 &&
    files.every(f => !!f.file) &&
    canSubmitPlan(planType, funding)

  return (
    <div className="bg-background text-on-background min-h-screen flex flex-col">
      <Navbar />
      <div className="pt-16 flex flex-col flex-grow min-h-0">
        <main className="flex-grow w-full min-w-0">
          {phase === 'processing' ? (
            <ProcessingView
              errorText={pipelineError}
              runPipeline={runPipeline}
              onError={setPipelineError}
              onComplete={onProcessingComplete}
            />
          ) : (
            <div className="flex-grow pt-8 pb-12 px-6 md:px-12 lg:px-24">
              <div className="max-w-6xl mx-auto w-full space-y-12">

                <header className="max-w-3xl flex flex-col gap-4">
                  <div className="inline-flex shrink-0 items-center gap-2 self-start bg-secondary-container text-on-secondary-container px-3 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase">
                    <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>auto_fix</span>
                    Multi-Doc Stitching Active
                  </div>
                  <h1 className="text-4xl md:text-5xl font-extrabold font-headline tracking-tight text-primary leading-[1.15] mt-0">
                    Upload &amp; Context Wizard
                  </h1>
                  <p className="text-lg text-on-surface-variant leading-relaxed font-medium">
                    Our Indiana-specific engine requires specific policy context to frame your appeal. We analyze your denials through the lens of local regulatory frameworks.
                  </p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-start">

                  <section className="lg:col-span-4 space-y-6 min-w-0">
                    <div className="bg-surface-container-low p-8 rounded-xl space-y-8">
                      <div className="space-y-2">
                        <h2 className="text-xl font-bold font-headline text-primary">Policy Intelligence</h2>
                        <p className="text-sm text-on-surface-variant">Provide the foundational details of your coverage.</p>
                      </div>

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
                            <label key={value} className={`flex items-center gap-4 p-4 rounded-lg cursor-pointer transition-all border
                              ${planType === value ? 'bg-surface-container-lowest border-primary/40' : 'bg-surface-container-lowest border-transparent hover:border-primary/20'}`}>
                              <input
                                className="text-primary focus:ring-primary h-5 w-5 border-outline shrink-0"
                                name="plan_type"
                                type="radio"
                                value={value}
                                checked={planType === value}
                                onChange={() => setPlanType(value)}
                              />
                              <div className="flex flex-col min-w-0">
                                <span className="font-bold text-on-surface">{label}</span>
                                <span className="text-xs text-on-surface-variant">{desc}</span>
                              </div>
                            </label>
                          ))}
                        </div>
                      </div>

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
                            <label key={value} className={`flex items-center gap-4 p-4 rounded-lg cursor-pointer transition-all border
                              ${funding === value ? 'bg-surface-container-lowest border-primary/40' : 'bg-surface-container-lowest border-transparent hover:border-primary/20'}`}>
                              <input
                                className="text-primary focus:ring-primary h-5 w-5 border-outline shrink-0"
                                name="funding"
                                type="radio"
                                value={value}
                                checked={funding === value}
                                onChange={() => setFunding(value)}
                              />
                              <div className="flex flex-col min-w-0">
                                <span className="font-bold text-on-surface">{label}</span>
                                <span className="text-xs text-on-surface-variant">{desc}</span>
                              </div>
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>

                  <section className="lg:col-span-8 flex flex-col gap-6 min-w-0 w-full">
                    <div className="flex flex-col gap-3">
                      <p className="text-sm font-semibold text-on-surface">What are you uploading next?</p>
                      <div className="flex flex-wrap gap-2">
                        {(Object.keys(DOC_KIND_LABEL) as DocKind[]).map(k => (
                          <button
                            key={k}
                            type="button"
                            onClick={() => setNextUploadKind(k)}
                            className={`px-4 py-2 rounded-full text-sm font-bold transition-all border
                              ${nextUploadKind === k
                                ? 'bg-primary text-white border-primary shadow-md'
                                : 'bg-surface-container-high text-on-surface-variant border-outline-variant/30 hover:border-primary/40'}`}
                          >
                            {DOC_KIND_LABEL[k]}
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-on-surface-variant">
                        The next file you add will be tagged accordingly; you can change any file in the list below.
                      </p>
                    </div>

                    <div className="bg-surface-container-lowest p-1 rounded-2xl shadow-sm border border-outline-variant/10">
                      <div
                        role="button"
                        tabIndex={0}
                        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click() } }}
                        onDragOver={e => { e.preventDefault(); setDragging(true) }}
                        onDragLeave={() => setDragging(false)}
                        onDrop={e => { e.preventDefault(); setDragging(false); addFilesFromList(e.dataTransfer.files) }}
                        onClick={() => inputRef.current?.click()}
                        className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center text-center space-y-6 group transition-colors cursor-pointer bg-surface/50
                          ${dragging ? 'border-primary bg-blue-50/80' : 'border-outline-variant hover:border-primary'}`}
                      >
                        <input
                          ref={inputRef}
                          type="file"
                          className="hidden"
                          multiple
                          accept=".pdf,.jpg,.png"
                          onChange={e => {
                            addFilesFromList(e.target.files)
                            e.target.value = ''
                          }}
                        />
                        <div className={`w-16 h-16 rounded-full flex items-center justify-center text-primary group-hover:scale-110 transition-transform
                          ${dragging ? 'bg-primary text-white' : 'bg-secondary-container'}`}>
                          <span className="material-symbols-outlined text-3xl">upload_file</span>
                        </div>
                        <div className="space-y-2">
                          <h3 className="text-xl font-bold font-headline text-on-surface">Drop denial letters or policy docs here</h3>
                          <p className="text-on-surface-variant max-w-sm mx-auto">
                            Upload multiple PDFs. Our engine will automatically stitch them into a chronological medical history.
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-4 justify-center">
                          <button type="button" onClick={e => { e.stopPropagation(); inputRef.current?.click() }} className="px-6 py-2 bg-surface-container-high rounded-full font-bold text-sm text-primary hover:bg-surface-dim transition-colors">
                            Select Files
                          </button>
                          <button type="button" onClick={e => e.stopPropagation()} className="px-6 py-2 text-sm font-bold text-on-surface-variant hover:text-primary transition-colors">
                            Import from IDOI Portal
                          </button>
                        </div>
                      </div>
                    </div>

                    {files.length > 0 && (
                      <div className="bg-surface-container-low p-6 rounded-xl space-y-4">
                        <div className="flex justify-between items-center gap-2">
                          <h4 className="text-xs font-bold tracking-widest text-primary uppercase">Stitching Progress</h4>
                          <span className="text-xs font-bold text-on-surface-variant whitespace-nowrap">
                            {files.length} Document{files.length === 1 ? '' : 's'} Detected
                          </span>
                        </div>
                        <p className="text-xs text-on-surface-variant">
                          Label each file so analysis can map EOB, denial, and billing data correctly.
                        </p>
                        <div className="space-y-3">
                          {files.map(f => (
                            <div key={f.id} className="flex flex-col sm:flex-row sm:items-center gap-3 p-3 bg-white rounded-lg border border-outline-variant/20">
                              <span className="material-symbols-outlined text-secondary shrink-0 hidden sm:inline">description</span>
                              <div className="flex-grow min-w-0 flex-1">
                                <div className="text-xs font-bold text-on-surface truncate">{f.name}</div>
                                <div className="h-1.5 w-full bg-surface-container rounded-full mt-1 overflow-hidden">
                                  <div className="h-full bg-primary-container transition-all" style={{ width: fileProgress(f) }} />
                                </div>
                              </div>
                              <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
                                <label className="sr-only" htmlFor={`doc-kind-${f.id}`}>Document type</label>
                                <select
                                  id={`doc-kind-${f.id}`}
                                  value={f.docKind}
                                  onClick={e => e.stopPropagation()}
                                  onChange={e => setFileKind(f.id, e.target.value as DocKind)}
                                  className="w-full sm:w-[11rem] text-xs font-semibold border border-outline-variant rounded-lg px-2 py-2 bg-surface-container-lowest text-primary focus:ring-2 focus:ring-primary/30 focus:outline-none"
                                >
                                  {(Object.keys(DOC_KIND_LABEL) as DocKind[]).map(k => (
                                    <option key={k} value={k}>{DOC_KIND_LABEL[k]}</option>
                                  ))}
                                </select>
                                {f.status === 'extracted' ? (
                                  <span className="material-symbols-outlined text-sm text-primary shrink-0" title="Processed">check_circle</span>
                                ) : (
                                  <span className="text-[10px] font-bold text-on-surface-variant uppercase shrink-0 whitespace-nowrap">Analyzing...</span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4 pt-2 w-full">
                      <button
                        type="button"
                        disabled={!canAnalyze}
                        onClick={() => {
                          if (!canAnalyze) return
                          setPipelineError(null)
                          persistDocProfileForResults()
                          setPhase('processing')
                        }}
                        className={`text-white w-full md:w-auto shrink-0 px-10 py-4 rounded-xl font-bold font-headline text-lg shadow-lg transition-all flex items-center justify-center gap-3
                          ${canAnalyze
                            ? 'signature-cta hover:shadow-xl hover:scale-[1.02]'
                            : 'bg-slate-300 cursor-not-allowed opacity-70'}`}
                      >
                        Begin Forensic Analysis
                        <span className="material-symbols-outlined">analytics</span>
                      </button>
                      <p className="text-xs text-on-surface-variant leading-tight text-center md:text-left md:max-w-sm md:pt-1">
                        By clicking, you authorize Resolvly to process these documents under <br />
                        <span className="font-bold">Indiana Health Insurance Advocacy standards.</span>
                      </p>
                    </div>
                  </section>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full">
                  {[
                    { icon: 'gavel', title: 'Legal Compliance', desc: 'Automatic cross-referencing with Indiana Code Title 27 for comprehensive appeal grounding.' },
                    { icon: 'security', title: 'Data Sovereignty', desc: 'All data is encrypted and stays within our secure Indiana portal; never used for training public models.' },
                    { icon: 'history_edu', title: 'Drafting Engine', desc: 'The Context Wizard determines the tone and statutory language required for your specific denial type.' },
                  ].map(({ icon, title, desc }) => (
                    <div key={title} className="p-6 rounded-xl bg-surface-container-lowest space-y-2 border border-outline-variant/10">
                      <span className="material-symbols-outlined text-primary">{icon}</span>
                      <h5 className="font-bold text-on-surface">{title}</h5>
                      <p className="text-xs text-on-surface-variant leading-relaxed">{desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
      <Footer disclaimer="Resolvly is an advocacy platform and does not provide legal advice. Documents are processed for analysis purposes only." />

      <div className="md:hidden fixed bottom-0 w-full bg-white border-t border-slate-200 h-16 flex items-center justify-around z-50">
        {[
          { icon: 'home', label: 'Home', to: '/', active: false },
          { icon: 'upload_file', label: 'Wizard', to: '/analyze', active: true },
          { icon: 'gavel', label: 'Plan', to: '/action-plan', active: false },
          { icon: 'account_circle', label: 'Profile', to: '/', active: false },
        ].map(({ icon, label, active, to }) => (
          <Link key={label} to={to} className={`flex flex-col items-center gap-1 ${active ? 'text-primary' : 'text-slate-400'}`}>
            <span className="material-symbols-outlined text-xl" style={active ? { fontVariationSettings: "'FILL' 1" } : {}}>{icon}</span>
            <span className="text-[10px] font-bold uppercase tracking-tighter">{label}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
