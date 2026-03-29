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

const DOC_KIND_CONFIG: Record<DocKind, { icon: string; title: string; desc: string }> = {
  denial: {
    icon: 'cancel',
    title: 'Denial Letter',
    desc: 'The official denial notice from your insurer',
  },
  eob: {
    icon: 'receipt_long',
    title: 'Explanation of Benefits',
    desc: 'EOB showing what your plan paid or denied',
  },
  medical_bill: {
    icon: 'local_hospital',
    title: 'Medical Bill',
    desc: 'Bill or itemized statement from hospital or provider',
  },
}

// The upload order we display cards in
const DOC_KIND_ORDER: DocKind[] = ['denial', 'eob', 'medical_bill']

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

// ─── Processing (after Begin Forensic Analysis) ──────────────────────────────
const PIPELINE_STAGES = [
  { id: 'extraction', label: 'Document text extracted', detail: null as string[] | null },
  { id: 'entities', label: 'Extracting claim identifiers, codes, dates, and amounts', detail: null },
  { id: 'codes', label: 'Resolving billing and denial codes (CMS / authoritative references)', detail: null },
  { id: 'federal', label: 'Searching federal regulations (eCFR)', detail: null },
  { id: 'state', label: 'Checking state DOI resources and routing', detail: null },
  { id: 'analysis', label: 'Running root cause and deadline analysis', detail: null },
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
    <div className="max-w-2xl mx-auto w-full py-8">
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

// ─── Single-page Upload & Context Wizard ────────────────────────────────────
export default function AnalyzeFlow() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<'wizard' | 'processing'>('wizard')

  const [files, setFiles] = useState<UploadedFile[]>([])
  // Track which card is being dragged over (for per-card drag highlight)
  const [draggingKind, setDraggingKind] = useState<DocKind | null>(null)
  const [pipelineError, setPipelineError] = useState<string | null>(null)

  const [planType, setPlanType] = useState<string>('')
  const [funding, setFunding] = useState<string>('')

  // One hidden file input per document type
  const denialRef = useRef<HTMLInputElement>(null)
  const eobRef = useRef<HTMLInputElement>(null)
  const medBillRef = useRef<HTMLInputElement>(null)

  function getInputRef(kind: DocKind): React.RefObject<HTMLInputElement | null> {
    if (kind === 'denial') return denialRef
    if (kind === 'eob') return eobRef
    return medBillRef
  }

  useEffect(() => {
    if (sessionStorage.getItem(RESOLVLY_ANALYSIS_COMPLETE_KEY) === '1') {
      navigate('/action-plan', { replace: true })
    }
  }, [navigate])

  /** Add (or replace) the file for the given document slot. Only the first file is used. */
  function addFileForKind(kind: DocKind, fileList: FileList | null) {
    if (!fileList?.length) return
    const file = fileList[0]
    const base = baseNameForKind(kind)
    setFiles(prev => {
      // Replace any existing file for this kind
      const filtered = prev.filter(f => f.docKind !== kind)
      const newEntry: UploadedFile = {
        id: crypto.randomUUID(),
        name: `${base}.pdf`,
        size: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
        type: typeLabelForKind(kind),
        status: 'extracted',
        docKind: kind,
        file,
      }
      return [...filtered, newEntry]
    })
  }

  function removeFileByKind(kind: DocKind) {
    setFiles(prev => prev.filter(f => f.docKind !== kind))
  }

  function getFileForKind(kind: DocKind): UploadedFile | undefined {
    return files.find(f => f.docKind === kind)
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

  // All 3 document types must be uploaded, plus plan selections filled
  const allDocsUploaded = DOC_KIND_ORDER.every(k => !!getFileForKind(k)?.file)
  const canAnalyze = allDocsUploaded && canSubmitPlan(planType, funding)

  // What's still missing (for helper text near the button)
  const missingDocs = DOC_KIND_ORDER.filter(k => !getFileForKind(k))
  const missingPlan = !planType
  const missingFunding = planType === 'employer' && !funding

  return (
    <div className="bg-background text-on-background selection:bg-secondary-container min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-grow w-full min-w-0 pt-24 pb-12">
        <div className="editorial-margin">
          {phase === 'processing' ? (
            <ProcessingView
              errorText={pipelineError}
              runPipeline={runPipeline}
              onError={setPipelineError}
              onComplete={onProcessingComplete}
            />
          ) : (
            <div className="w-full space-y-12">

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

                  {/* ── Left column: Policy Intelligence ── */}
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

                  {/* ── Right column: Document Upload ── */}
                  <section className="lg:col-span-8 flex flex-col gap-6 min-w-0 w-full">

                    <div className="space-y-2">
                      <h2 className="text-xl font-bold font-headline text-primary">Upload Your Documents</h2>
                      <p className="text-sm text-on-surface-variant">
                        All three documents are required for a complete forensic analysis. Click each card to upload the corresponding file.
                      </p>
                    </div>

                    {/* ── 3 Document Upload Cards ── */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      {DOC_KIND_ORDER.map(kind => {
                        const config = DOC_KIND_CONFIG[kind]
                        const uploaded = getFileForKind(kind)
                        const isUploaded = !!uploaded
                        const isDraggingOver = draggingKind === kind

                        return (
                          <div
                            key={kind}
                            role="button"
                            tabIndex={0}
                            aria-label={`Upload ${config.title}`}
                            onKeyDown={e => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                getInputRef(kind).current?.click()
                              }
                            }}
                            onDragOver={e => { e.preventDefault(); setDraggingKind(kind) }}
                            onDragLeave={() => setDraggingKind(null)}
                            onDrop={e => {
                              e.preventDefault()
                              setDraggingKind(null)
                              addFileForKind(kind, e.dataTransfer.files)
                            }}
                            onClick={() => getInputRef(kind).current?.click()}
                            className={`relative flex flex-col rounded-xl border-2 cursor-pointer transition-all duration-200 overflow-hidden
                              ${isUploaded
                                ? 'bg-emerald-50 border-emerald-400 shadow-sm'
                                : isDraggingOver
                                  ? 'bg-blue-50 border-primary border-solid scale-[1.02] shadow-md'
                                  : 'bg-surface-container-lowest border-outline-variant/40 border-dashed hover:border-primary/60 hover:bg-primary/5'
                              }`}
                          >
                            {/* Hidden file input for this slot */}
                            <input
                              ref={getInputRef(kind) as React.RefObject<HTMLInputElement>}
                              type="file"
                              className="hidden"
                              accept=".pdf,.jpg,.jpeg,.png"
                              onChange={e => {
                                addFileForKind(kind, e.target.files)
                                e.target.value = ''
                              }}
                            />

                            {isUploaded ? (
                              /* ── Uploaded (green) state ── */
                              <div className="flex flex-col h-full p-5 gap-3">
                                <div className="flex items-start justify-between">
                                  <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                                    <span className="material-symbols-outlined text-emerald-600 text-xl">check_circle</span>
                                  </div>
                                  <button
                                    type="button"
                                    aria-label={`Remove ${config.title}`}
                                    onClick={e => { e.stopPropagation(); removeFileByKind(kind) }}
                                    className="w-7 h-7 rounded-full bg-emerald-100 hover:bg-emerald-200 flex items-center justify-center transition-colors shrink-0"
                                  >
                                    <span className="material-symbols-outlined text-emerald-600 text-sm">close</span>
                                  </button>
                                </div>
                                <div className="flex-grow min-w-0">
                                  <p className="text-xs font-bold uppercase tracking-wide text-emerald-600 mb-1">Uploaded</p>
                                  <p className="font-bold text-sm text-emerald-900 leading-tight">{config.title}</p>
                                  <p className="text-xs text-emerald-700 mt-2 truncate">{uploaded.name}</p>
                                  <p className="text-xs text-emerald-500 mt-0.5">{uploaded.size}</p>
                                </div>
                                <p className="text-xs text-emerald-600 font-medium flex items-center gap-1 mt-auto">
                                  <span className="material-symbols-outlined text-sm">edit</span>
                                  Click to replace
                                </p>
                              </div>
                            ) : (
                              /* ── Empty (blue) state ── */
                              <div className="flex flex-col items-center text-center p-5 py-8 gap-4 h-full">
                                <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors
                                  ${isDraggingOver ? 'bg-primary text-white' : 'bg-primary/10'}`}>
                                  <span className={`material-symbols-outlined text-2xl ${isDraggingOver ? 'text-white' : 'text-primary'}`}>
                                    {config.icon}
                                  </span>
                                </div>
                                <div className="space-y-1">
                                  <p className="font-bold text-sm text-on-surface">{config.title}</p>
                                  <p className="text-xs text-on-surface-variant leading-relaxed">{config.desc}</p>
                                </div>
                                <div className="mt-auto text-xs font-semibold text-primary flex items-center gap-1 pt-2">
                                  <span className="material-symbols-outlined text-sm">upload</span>
                                  {isDraggingOver ? 'Drop here' : 'Click or drag to upload'}
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>

                    {/* ── Upload progress summary ── */}
                    <div className="flex items-center gap-3 px-1">
                      {DOC_KIND_ORDER.map(kind => {
                        const isUploaded = !!getFileForKind(kind)
                        return (
                          <div key={kind} className="flex items-center gap-1.5 text-xs font-semibold">
                            <span className={`material-symbols-outlined text-base ${isUploaded ? 'text-emerald-500' : 'text-slate-300'}`}>
                              {isUploaded ? 'check_circle' : 'radio_button_unchecked'}
                            </span>
                            <span className={isUploaded ? 'text-emerald-700' : 'text-slate-400'}>
                              {DOC_KIND_LABEL[kind]}
                            </span>
                          </div>
                        )
                      })}
                      <span className="ml-auto text-xs text-on-surface-variant font-medium">
                        {files.length}/3 uploaded
                      </span>
                    </div>

                    {/* ── Begin Forensic Analysis button + helper text ── */}
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

                      {/* Helper text explaining what's still needed */}
                      <div className="text-xs text-on-surface-variant leading-relaxed text-center md:text-left md:max-w-xs md:pt-1 space-y-1">
                        {!canAnalyze ? (
                          <div className="space-y-1">
                            {missingDocs.length > 0 && (
                              <p className="text-amber-600 font-semibold flex items-center gap-1">
                                <span className="material-symbols-outlined text-sm">info</span>
                                Still needed: {missingDocs.map(k => DOC_KIND_CONFIG[k].title).join(', ')}
                              </p>
                            )}
                            {missingPlan && (
                              <p className="text-amber-600 font-semibold flex items-center gap-1">
                                <span className="material-symbols-outlined text-sm">info</span>
                                Select a plan type
                              </p>
                            )}
                            {missingFunding && (
                              <p className="text-amber-600 font-semibold flex items-center gap-1">
                                <span className="material-symbols-outlined text-sm">info</span>
                                Select a funding structure
                              </p>
                            )}
                          </div>
                        ) : (
                          <p>
                            By clicking, you authorize Resolvly to process these documents under{' '}
                            <span className="font-bold">Indiana Health Insurance Advocacy standards.</span>
                          </p>
                        )}
                      </div>
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
          )}
        </div>
      </main>
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
