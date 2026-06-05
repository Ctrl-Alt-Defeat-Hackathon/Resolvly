import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import DreelioNav from '../components/marketing/DreelioNav'
import DreelioFooter from '../components/marketing/DreelioFooter'
import { uploadDocuments, extractEntities, analyzeClaim, wizardPlanType } from '../lib/api'
import { buildPlanContext, buildWizardBody, canSubmitPlan } from '../lib/planMapping'
import {
  DEMO_CASES,
  DEMO_CASE_SESSION_KEY,
  fetchDemoCaseFiles,
  fetchDemoFile,
  type DemoCaseId,
} from '../lib/demoDocuments'
import { STORAGE_KEYS, saveAnalysisBundle, clearAnalysisSession, hasActiveAnalysis } from '../lib/sessionKeys'
import { prefetchActionPlanOutputs, prefetchSecondaryOutputs, clearAllOutputsCache } from '../lib/outputsCache'
import { viewTransitionNavigate } from '../lib/viewTransitionNavigate'

export const RESOLVLY_ANALYSIS_COMPLETE_KEY = STORAGE_KEYS.ANALYSIS_COMPLETE

export type DocKind = 'eob' | 'denial' | 'medical_bill'

const DOC_KIND_CONFIG: Record<DocKind, { icon: string; title: string; desc: string }> = {
  denial:       { icon: 'cancel',         title: 'Denial Letter',           desc: 'The official denial notice from your insurer' },
  eob:          { icon: 'receipt_long',   title: 'Explanation of Benefits', desc: 'EOB showing what your plan paid or denied' },
  medical_bill: { icon: 'local_hospital', title: 'Medical Bill',            desc: 'Bill or itemized statement from your provider' },
}

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

function baseNameForKind(k: DocKind) {
  if (k === 'denial') return 'Denial_Letter'
  if (k === 'eob') return 'EOB'
  return 'Medical_Bill'
}
function typeLabelForKind(k: DocKind) {
  if (k === 'denial') return 'Denial Letter'
  if (k === 'eob') return 'Explanation of Benefits'
  return 'Medical Bill'
}

// ─── Pipeline stages ──────────────────────────────────────────────────────────
const PIPELINE_STAGES = [
  { id: 'upload',     label: 'Uploading documents to secure analysis server' },
  { id: 'extraction', label: 'Document text extracted' },
  { id: 'entities',   label: 'Extracting claim identifiers, codes, dates, and amounts' },
  { id: 'codes',      label: 'Resolving billing and denial codes (CMS / authoritative references)' },
  { id: 'federal',    label: 'Searching federal regulations (eCFR)' },
  { id: 'state',      label: 'Checking state DOI resources and routing' },
  { id: 'analysis',   label: 'Running root cause and deadline analysis' },
  { id: 'generating', label: 'Saving your results' },
]

// ─── Processing View ──────────────────────────────────────────────────────────
function ProcessingView({ completedCount, done, errorText }: {
  completedCount: number
  done: boolean
  errorText: string | null
}) {
  const progress = Math.round((completedCount / PIPELINE_STAGES.length) * 100)
  return (
    <div className="processing-shell">
      <div style={{ marginBottom: 40 }}>
        <span className="wizard-kicker">
          {done ? 'Complete' : errorText ? 'Error' : 'Analyzing'}
        </span>
        <h1 className="h-xl" style={{ color: 'var(--ink)', margin: '0 0 12px' }}>
          {done ? 'Analysis complete.' : errorText ? 'Analysis failed' : 'Analyzing your claim…'}
        </h1>
        <p className="body" style={{ color: 'var(--ink-2)', margin: 0 }}>
          {errorText
            ? <span style={{ color: 'var(--error)' }}>{errorText}</span>
            : done
              ? 'Loading your results…'
              : 'Working through each step — in under 20 seconds.'}
        </p>
      </div>

      <div className="processing-card">
        <div className="processing-bar-track">
          <div className="processing-bar-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="processing-stages">
          {PIPELINE_STAGES.map((stage, i) => {
            const isDone   = i < completedCount
            const isActive = i === completedCount && !done && !errorText
            const isPending = i > completedCount
            return (
              <div key={stage.id} className={`stage-row${isPending ? ' is-pending' : ''}`}>
                <span className="stage-icon-wrap" style={{ flexShrink: 0, marginTop: 2 }}>
                  {isDone  && <span className="ms" style={{ fontSize: 20, color: 'var(--emerald)' }}>check_circle</span>}
                  {isActive && <span className="ms wiz-spin" style={{ fontSize: 20, color: 'var(--accent)' }}>progress_activity</span>}
                  {isPending && <span className="stage-dot" />}
                </span>
                <p style={{
                  fontSize: 14,
                  fontWeight: isActive ? 700 : 400,
                  color: isDone ? 'var(--ink)' : isActive ? 'var(--accent)' : 'var(--ink-2)',
                  margin: 0,
                  lineHeight: 1.5,
                }}>
                  {stage.label}
                </p>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Step 0 — Plan Type ───────────────────────────────────────────────────────
const PLAN_TYPES = [
  { value: 'employer',  icon: 'business',         label: 'Employer-Sponsored',      desc: 'Coverage provided through your workplace' },
  { value: 'individual', icon: 'person',           label: 'Individual / Marketplace', desc: 'Marketplace or privately purchased plan' },
  { value: 'medicaid',  icon: 'health_and_safety', label: 'Medicaid',                desc: 'State-sponsored healthcare assistance' },
]

function StepPlanType({ planType, onSelect }: { planType: string; onSelect: (v: string) => void }) {
  return (
    <div>
      <span className="wizard-kicker">Step 1 of 3</span>
      <h1 className="h-xl" style={{ color: 'var(--ink)', margin: '0 0 12px' }}>
        What kind of plan is this?
      </h1>
      <p className="body" style={{ color: 'var(--ink-2)', margin: 0 }}>
        The plan type determines which regulations govern your appeal.
      </p>
      <div className="plan-grid">
        {PLAN_TYPES.map(({ value, icon, label, desc }) => (
          <button
            key={value}
            type="button"
            className={`plan-card${planType === value ? ' is-selected' : ''}`}
            onClick={() => onSelect(value)}
          >
            <div className="plan-card-icon">
              <span className="ms" style={{ fontSize: 28 }}>{icon}</span>
            </div>
            <p className="plan-card-title">{label}</p>
            <p className="plan-card-desc">{desc}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── Step 1 — Funding Structure ───────────────────────────────────────────────
const FUNDING_OPTIONS = [
  {
    value: 'erisa',
    icon: 'account_balance',
    label: 'Self-funded (ERISA)',
    desc: 'Your employer directly funds claims. Governed by federal ERISA law, not Indiana state insurance rules.',
  },
  {
    value: 'insured',
    icon: 'shield',
    label: 'Fully Insured',
    desc: 'An insurance company funds the claims. Subject to Indiana Department of Insurance (IDOI) regulations.',
  },
]

function StepFunding({
  planType, funding, onSelect, onNext, onSkip, onBack,
}: {
  planType: string
  funding: string
  onSelect: (v: string) => void
  onNext: () => void
  onSkip: () => void
  onBack: () => void
}) {
  const isRequired = planType === 'employer'
  return (
    <div>
      <button type="button" className="wizard-back-btn wizard-back-btn--inline" onClick={onBack}>
        <span className="ms" style={{ fontSize: 18 }}>arrow_back</span>
        Back
      </button>
      <span className="wizard-kicker">Step 2 of 3</span>
      <h1 className="h-xl" style={{ color: 'var(--ink)', margin: '0 0 12px' }}>
        What's the funding structure?
      </h1>
      <p className="body" style={{ color: 'var(--ink-2)', margin: 0 }}>
        {isRequired
          ? 'Required for employer plans — this determines whether federal or state law governs your appeal.'
          : 'Optional — helps us frame your appeal more precisely. You can skip if unsure.'}
      </p>

      <div className="option-grid">
        {FUNDING_OPTIONS.map(({ value, icon, label, desc }) => (
          <button
            key={value}
            type="button"
            className={`option-card${funding === value ? ' is-selected' : ''}`}
            onClick={() => onSelect(value)}
          >
            <div className="option-card-icon">
              <span className="ms" style={{ fontSize: 22 }}>{icon}</span>
            </div>
            <p className="option-card-title">{label}</p>
            <p className="option-card-desc">{desc}</p>
          </button>
        ))}
      </div>

      <div className="wizard-nav">
        {!isRequired && (
          <button type="button" className="btn btn-ghost" onClick={onSkip}>
            Skip for now
          </button>
        )}
        <button
          type="button"
          className="btn btn-primary"
          disabled={isRequired && !funding}
          onClick={onNext}
          style={isRequired && !funding ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
        >
          Continue
          <span className="ms arrow" style={{ fontSize: 18 }}>arrow_forward</span>
        </button>
      </div>
    </div>
  )
}

// ─── Step 2 — Document Upload ─────────────────────────────────────────────────
function StepUpload({
  files,
  draggingKind,
  demoMode,
  activeDemoCase,
  demoLoading,
  demoError,
  planType,
  funding,
  onUploadClick,
  onRemove,
  onDragOver,
  onDragLeave,
  onDrop,
  onDemoCase,
  onBeginAnalysis,
  onBack,
  inputRefs,
}: {
  files: UploadedFile[]
  draggingKind: DocKind | null
  demoMode: boolean
  activeDemoCase: DemoCaseId
  demoLoading: DocKind | DemoCaseId | null
  demoError: string | null
  planType: string
  funding: string
  onUploadClick: (kind: DocKind) => void
  onRemove: (kind: DocKind) => void
  onDragOver: (kind: DocKind) => void
  onDragLeave: () => void
  onDrop: (kind: DocKind, files: FileList) => void
  onDemoCase: (id: DemoCaseId) => void
  onBeginAnalysis: () => void
  onBack: () => void
  inputRefs: Record<DocKind, React.RefObject<HTMLInputElement | null>>
}) {
  const getFile = (k: DocKind) => files.find(f => f.docKind === k)
  const allUploaded = DOC_KIND_ORDER.every(k => !!getFile(k)?.file)
  const canAnalyze  = allUploaded && canSubmitPlan(planType, funding)

  const missingDocs    = DOC_KIND_ORDER.filter(k => !getFile(k))
  const missingPlan    = !planType
  const missingFunding = planType === 'employer' && !funding

  return (
    <div>
      <button type="button" className="wizard-back-btn wizard-back-btn--inline" onClick={onBack}>
        <span className="ms" style={{ fontSize: 18 }}>arrow_back</span>
        Back
      </button>
      <span className="wizard-kicker">Step 3 of 3</span>
      <h1 className="h-xl" style={{ color: 'var(--ink)', margin: '0 0 12px' }}>
        Upload your documents
      </h1>
      <p className="body" style={{ color: 'var(--ink-2)', margin: 0 }}>
        {demoMode
          ? 'Select a demo case to load all three sample files instantly.'
          : 'All three documents are required for a complete forensic analysis.'}
      </p>

      {/* Demo case selector */}
      {demoMode && (
        <div style={{ marginTop: 24 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink-2)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Demo case
          </p>
          <div className="demo-case-row">
            {DEMO_CASES.map(dc => (
              <button
                key={dc.id}
                type="button"
                disabled={!!demoLoading}
                className={`demo-case-pill${activeDemoCase === dc.id ? ' is-active' : ''}`}
                onClick={() => onDemoCase(dc.id)}
              >
                {demoLoading === dc.id
                  ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <span className="ms wiz-spin" style={{ fontSize: 14 }}>progress_activity</span>
                      Loading…
                    </span>
                  : dc.label}
              </button>
            ))}
          </div>
          {demoError && (
            <p style={{ fontSize: 12, color: 'var(--error)', marginTop: 8 }}>{demoError}</p>
          )}
        </div>
      )}

      {/* Upload cards */}
      <div className="upload-grid">
        {DOC_KIND_ORDER.map(kind => {
          const config    = DOC_KIND_CONFIG[kind]
          const uploaded  = getFile(kind)
          const isUploaded = !!uploaded
          const isDragging = draggingKind === kind

          return (
            <div key={kind} style={{ position: 'relative' }}>
              <input
                ref={inputRefs[kind] as React.RefObject<HTMLInputElement>}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                className="hidden"
                style={{ display: 'none' }}
                onChange={e => {
                  if (!e.target.files?.length) return
                  onDrop(kind, e.target.files)
                  e.target.value = ''
                }}
              />
              <button
                type="button"
                className={[
                  'upload-card',
                  isUploaded ? 'is-uploaded' : '',
                  isDragging ? 'is-dragging' : '',
                  demoMode && !isUploaded ? 'is-demo' : '',
                ].filter(Boolean).join(' ')}
                onDragOver={e => { e.preventDefault(); if (!demoMode) onDragOver(kind) }}
                onDragLeave={onDragLeave}
                onDrop={e => {
                  e.preventDefault()
                  if (!demoMode && e.dataTransfer.files.length) {
                    onDrop(kind, e.dataTransfer.files)
                    onDragLeave()
                  }
                }}
                onClick={() => {
                  if (demoMode) { onUploadClick(kind); return }
                  inputRefs[kind].current?.click()
                }}
              >
                {isUploaded ? (
                  <>
                    <div className="upload-card-icon">
                      <span className="ms" style={{ fontSize: 22 }}>check_circle</span>
                    </div>
                    <p style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--emerald)', margin: 0 }}>Uploaded</p>
                    <p style={{ fontSize: 15, fontWeight: 700, color: '#14532d', margin: '4px 0 0' }}>{config.title}</p>
                    <p style={{ fontSize: 12, color: '#166534', margin: '6px 0 0', wordBreak: 'break-all', lineHeight: 1.4 }}>{uploaded.name}</p>
                    <p style={{ fontSize: 11, color: '#15803d', margin: '2px 0 0' }}>{uploaded.size}</p>
                    <button
                      type="button"
                      onClick={e => { e.stopPropagation(); onRemove(kind) }}
                      style={{
                        marginTop: 10, padding: '4px 12px', borderRadius: 'var(--r-pill)',
                        border: '1px solid #86efac', background: '#fff', color: '#166534',
                        fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font)',
                      }}
                    >
                      Replace
                    </button>
                  </>
                ) : (
                  <>
                    <div className="upload-card-icon">
                      <span className="ms" style={{ fontSize: 24 }}>
                        {demoLoading === kind ? 'progress_activity' : demoMode ? 'play_circle' : config.icon}
                      </span>
                    </div>
                    <p style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>{config.title}</p>
                    <p style={{ fontSize: 12, color: 'var(--ink-2)', margin: '4px 0 0', lineHeight: 1.5 }}>{config.desc}</p>
                    <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', margin: '10px 0 0', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span className={`ms${demoLoading === kind ? ' wiz-spin' : ''}`} style={{ fontSize: 14 }}>
                        {demoLoading === kind ? 'progress_activity' : demoMode ? 'play_circle' : isDragging ? 'download' : 'upload'}
                      </span>
                      {demoLoading === kind ? 'Loading…' : demoMode ? 'Click to load demo' : isDragging ? 'Drop here' : 'Click or drag to upload'}
                    </p>
                  </>
                )}
              </button>
            </div>
          )
        })}
      </div>

      {/* Status row */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginTop: 16, flexWrap: 'wrap' }}>
        {DOC_KIND_ORDER.map(kind => {
          const ok = !!getFile(kind)
          return (
            <span key={kind} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600 }}>
              <span className="ms" style={{ fontSize: 16, color: ok ? 'var(--emerald)' : 'rgba(33,29,22,0.2)' }}>
                {ok ? 'check_circle' : 'radio_button_unchecked'}
              </span>
              <span style={{ color: ok ? 'var(--emerald-ink)' : 'var(--ink-3)' }}>
                {DOC_KIND_CONFIG[kind].title}
              </span>
            </span>
          )
        })}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--ink-2)', fontWeight: 500 }}>
          {files.length}/3 uploaded
        </span>
      </div>

      {/* CTA + validation */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 40 }}>
        <button
          type="button"
          disabled={!canAnalyze}
          onClick={() => { if (canAnalyze) onBeginAnalysis() }}
          className="btn btn-primary"
          style={{
            fontSize: 17, padding: '16px 36px', borderRadius: 'var(--r-pill)',
            boxShadow: canAnalyze ? 'var(--sh-navy)' : 'none',
            opacity: canAnalyze ? 1 : 0.45,
            cursor: canAnalyze ? 'pointer' : 'not-allowed',
            alignSelf: 'flex-start',
          }}
        >
          Begin Forensic Analysis
          <span className="ms arrow" style={{ fontSize: 20 }}>analytics</span>
        </button>

        {!canAnalyze && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {missingDocs.length > 0 && (
              <p style={{ fontSize: 13, color: 'var(--amber-ink)', fontWeight: 600, margin: 0, display: 'flex', gap: 5, alignItems: 'center' }}>
                <span className="ms" style={{ fontSize: 15 }}>info</span>
                Still needed: {missingDocs.map(k => DOC_KIND_CONFIG[k].title).join(', ')}
              </p>
            )}
            {missingPlan && (
              <p style={{ fontSize: 13, color: 'var(--amber-ink)', fontWeight: 600, margin: 0, display: 'flex', gap: 5, alignItems: 'center' }}>
                <span className="ms" style={{ fontSize: 15 }}>info</span>
                Select a plan type (go back to step 1)
              </p>
            )}
            {missingFunding && (
              <p style={{ fontSize: 13, color: 'var(--amber-ink)', fontWeight: 600, margin: 0, display: 'flex', gap: 5, alignItems: 'center' }}>
                <span className="ms" style={{ fontSize: 15 }}>info</span>
                Select a funding structure (go back to step 2)
              </p>
            )}
          </div>
        )}
        {canAnalyze && (
          <p style={{ fontSize: 12, color: 'var(--ink-2)', margin: 0 }}>
            By clicking, you authorize Resolvly to process these documents under{' '}
            <strong>Indiana Health Insurance Advocacy standards.</strong>
          </p>
        )}
      </div>
    </div>
  )
}

// ─── Main Wizard ──────────────────────────────────────────────────────────────
export default function AnalyzeFlow({ isDemo = false }: { isDemo?: boolean }) {
  const navigate = useNavigate()

  // Wizard step nav
  const [step, setStep]       = useState(0)
  const [animDir, setAnimDir] = useState<'fwd' | 'back'>('fwd')

  // Phase: wizard steps vs running pipeline
  const [phase, setPhase] = useState<'wizard' | 'processing'>('wizard')

  // Plan context
  const [planType, setPlanType] = useState('')
  const [funding, setFunding]   = useState('')

  // Files
  const [files, setFiles]           = useState<UploadedFile[]>([])
  const [draggingKind, setDraggingKind] = useState<DocKind | null>(null)

  // Demo state
  const [demoMode]  = useState(isDemo)
  const [activeDemoCase, setActiveDemoCase] = useState<DemoCaseId>(() => {
    const saved = sessionStorage.getItem(DEMO_CASE_SESSION_KEY) as DemoCaseId | null
    return saved && DEMO_CASES.some(c => c.id === saved) ? saved : 'default'
  })
  const [demoLoading, setDemoLoading] = useState<DocKind | DemoCaseId | null>(null)
  const [demoError, setDemoError]     = useState<string | null>(null)

  // Pipeline
  const [pipelineError, setPipelineError] = useState<string | null>(null)
  const [completedCount, setCompletedCount] = useState(0)
  const [pipelineDone, setPipelineDone]     = useState(false)
  const pipelineRunningRef = useRef(false)
  const pipelineCancelledRef = useRef(false)
  const finishTimerRef = useRef<number | null>(null)

  const hasWizardProgress =
    phase === 'processing' ||
    step > 0 ||
    files.length > 0 ||
    planType !== '' ||
    funding !== ''
  const shouldConfirmLeave = hasActiveAnalysis() || hasWizardProgress

  useEffect(() => {
    pipelineCancelledRef.current = false
    return () => {
      pipelineCancelledRef.current = true
      if (finishTimerRef.current != null) {
        window.clearTimeout(finishTimerRef.current)
        finishTimerRef.current = null
      }
    }
  }, [])

  function handleConfirmLeaveHome() {
    pipelineCancelledRef.current = true
    if (finishTimerRef.current != null) {
      window.clearTimeout(finishTimerRef.current)
      finishTimerRef.current = null
    }
    clearAnalysisSession()
    clearAllOutputsCache()
    viewTransitionNavigate(navigate, '/')
  }

  // File input refs
  const denialRef   = useRef<HTMLInputElement>(null)
  const eobRef      = useRef<HTMLInputElement>(null)
  const medBillRef  = useRef<HTMLInputElement>(null)
  const inputRefs: Record<DocKind, React.RefObject<HTMLInputElement | null>> = {
    denial: denialRef, eob: eobRef, medical_bill: medBillRef,
  }

  useEffect(() => {
    if (sessionStorage.getItem(RESOLVLY_ANALYSIS_COMPLETE_KEY) === '1' && !hasWizardProgress) {
      navigate('/action-plan', { replace: true })
    }
  }, [navigate, hasWizardProgress])

  // ─ File helpers ─
  function applyFileForKind(kind: DocKind, file: File, displayName?: string) {
    setFiles(prev => {
      const filtered = prev.filter(f => f.docKind !== kind)
      return [...filtered, {
        id: crypto.randomUUID(),
        name: displayName ?? file.name ?? `${baseNameForKind(kind)}.pdf`,
        size: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
        type: typeLabelForKind(kind),
        status: 'extracted' as const,
        docKind: kind,
        file,
      }]
    })
  }

  function applyAllDemoFiles(caseFiles: Record<DocKind, File>) {
    setFiles(prev => {
      const filtered = prev.filter(f => !DOC_KIND_ORDER.includes(f.docKind))
      return [...filtered, ...DOC_KIND_ORDER.map(kind => ({
        id: crypto.randomUUID(),
        name: caseFiles[kind].name ?? `${baseNameForKind(kind)}.pdf`,
        size: `${(caseFiles[kind].size / 1024 / 1024).toFixed(2)} MB`,
        type: typeLabelForKind(kind),
        status: 'extracted' as const,
        docKind: kind,
        file: caseFiles[kind],
      }))]
    })
  }

  function removeFileByKind(kind: DocKind) {
    setFiles(prev => prev.filter(f => f.docKind !== kind))
  }

  function addFileFromInput(kind: DocKind, fileList: FileList | null) {
    if (!fileList?.length) return
    applyFileForKind(kind, fileList[0])
  }

  // ─ Upload click handler ─
  async function handleUploadClick(kind: DocKind) {
    if (demoMode) {
      setDemoError(null)
      setDemoLoading(kind)
      try {
        const file = await fetchDemoFile(activeDemoCase, kind)
        applyFileForKind(kind, file)
      } catch (e) {
        setDemoError(e instanceof Error ? e.message : String(e))
      } finally {
        setDemoLoading(null)
      }
      return
    }
    inputRefs[kind].current?.click()
  }

  async function handleDemoCase(caseId: DemoCaseId) {
    setDemoError(null)
    setDemoLoading(caseId)
    setActiveDemoCase(caseId)
    sessionStorage.setItem(DEMO_CASE_SESSION_KEY, caseId)
    try {
      const caseFiles = await fetchDemoCaseFiles(caseId)
      applyAllDemoFiles(caseFiles)
    } catch (e) {
      setDemoError(e instanceof Error ? e.message : String(e))
    } finally {
      setDemoLoading(null)
    }
  }

  // ─ Navigation ─
  function goNext() {
    setAnimDir('fwd')
    setStep(s => s + 1)
  }
  function goBack() {
    setAnimDir('back')
    setStep(s => s - 1)
  }

  function handlePlanTypeSelect(value: string) {
    setPlanType(value)
    goNext()
  }

  // ─ Pipeline ─
  function persistDocProfile() {
    sessionStorage.setItem(STORAGE_KEYS.DOC_PROFILE, JSON.stringify({
      files: files.map(f => ({ id: f.id, name: f.name, docKind: f.docKind })),
      kindsPresent: {
        eob:          files.some(f => f.docKind === 'eob'),
        denial:       files.some(f => f.docKind === 'denial'),
        medical_bill: files.some(f => f.docKind === 'medical_bill'),
      },
    }))
  }

  const finishAndNavigate = useCallback(() => {
    if (pipelineCancelledRef.current) return
    sessionStorage.setItem(RESOLVLY_ANALYSIS_COMPLETE_KEY, '1')
    persistDocProfile()
    navigate('/action-plan')
  }, [navigate, files])

  const runPipeline = useCallback(async () => {
    if (pipelineRunningRef.current || pipelineCancelledRef.current) return
    pipelineRunningRef.current = true

    const plan_context = buildPlanContext(planType, funding)
    const fileBlobs = files.map(f => f.file).filter((x): x is File => !!x)
    if (!fileBlobs.length) {
      pipelineRunningRef.current = false
      throw new Error('Each file must be a real upload from your device.')
    }

    try {
      setCompletedCount(0)
      const up = await uploadDocuments(fileBlobs)
      if (pipelineCancelledRef.current) return
      setCompletedCount(1)

      const documents = up.documents.map(d => ({ doc_id: d.doc_id, text_extracted: d.text_extracted }))
      const ext = await extractEntities({
        upload_id: up.upload_id,
        documents,
        plan_context: plan_context as Record<string, unknown>,
      })
      if (pipelineCancelledRef.current) return
      setCompletedCount(3)

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
      if (pipelineCancelledRef.current) return
      setCompletedCount(6)

      const analyzed = await analyzeClaim(
        ext.claim_object as Record<string, unknown>,
        plan_context as Record<string, unknown>,
      )
      if (pipelineCancelledRef.current) return
      setCompletedCount(7)

      saveAnalysisBundle({
        claim_object: analyzed.claim_object,
        analysis: analyzed.analysis,
        enrichment: analyzed.enrichment,
        sources: analyzed.sources,
        plan_context: plan_context as Record<string, unknown>,
        wizard,
      })
      setCompletedCount(PIPELINE_STAGES.length)
      setPipelineDone(true)

      const co = analyzed.claim_object as Record<string, unknown>
      const an = analyzed.analysis as Record<string, unknown>
      const en = analyzed.enrichment as Record<string, unknown>
      void prefetchActionPlanOutputs(co, an, en).then(() => prefetchSecondaryOutputs(co, an, en))

      finishTimerRef.current = window.setTimeout(() => {
        finishTimerRef.current = null
        finishAndNavigate()
      }, 400)
    } finally {
      pipelineRunningRef.current = false
    }
  }, [files, planType, funding, finishAndNavigate])

  const beginAnalysis = useCallback(() => {
    pipelineCancelledRef.current = false
    sessionStorage.removeItem(RESOLVLY_ANALYSIS_COMPLETE_KEY)
    setPipelineError(null)
    setCompletedCount(0)
    setPipelineDone(false)
    setPhase('processing')
    void runPipeline().catch(e => {
      if (pipelineCancelledRef.current) return
      setPipelineError(e instanceof Error ? e.message : String(e))
    })
  }, [runPipeline])

  // ─ Render ─
  const stepClass = `wiz-enter-${animDir}`

  return (
    <div
      className="dreelio-landing wizard-shell"
      style={{ background: 'var(--canvas)' }}
    >
      <DreelioNav
        onStart={() => {}}
        confirmLeaveHome={shouldConfirmLeave}
        onConfirmLeaveHome={handleConfirmLeaveHome}
      />

      <main style={{ display: 'flex', flexDirection: 'column', minHeight: 'calc(100vh - 80px)' }}>
        <div className="wizard-layout" style={{ flex: 1 }}>
          {phase === 'processing' ? (
            <ProcessingView
              completedCount={completedCount}
              done={pipelineDone}
              errorText={pipelineError}
            />
          ) : (
            <>
              {/* Step header: back + dots */}
              <div className="wizard-header">
                {step > 0 ? (
                  <button type="button" className="wizard-back-btn" onClick={goBack}>
                    <span className="ms" style={{ fontSize: 18 }}>arrow_back</span>
                    Back
                  </button>
                ) : (
                  <span />
                )}
                <div className="wizard-dots">
                  {[0, 1, 2].map(i => (
                    <span
                      key={i}
                      className={`wizard-dot${i === step ? ' active' : i < step ? ' done' : ''}`}
                    />
                  ))}
                </div>
                <span className="wizard-back-spacer" />
              </div>

              {/* Animated step content */}
              <div key={step} className={stepClass}>
                {step === 0 && (
                  <StepPlanType planType={planType} onSelect={handlePlanTypeSelect} />
                )}
                {step === 1 && (
                  <StepFunding
                    planType={planType}
                    funding={funding}
                    onSelect={setFunding}
                    onNext={goNext}
                    onSkip={() => { setFunding(''); goNext() }}
                    onBack={goBack}
                  />
                )}
                {step === 2 && (
                  <StepUpload
                    files={files}
                    draggingKind={draggingKind}
                    demoMode={demoMode}
                    activeDemoCase={activeDemoCase}
                    demoLoading={demoLoading}
                    demoError={demoError}
                    planType={planType}
                    funding={funding}
                    onUploadClick={kind => void handleUploadClick(kind)}
                    onRemove={removeFileByKind}
                    onDragOver={setDraggingKind}
                    onDragLeave={() => setDraggingKind(null)}
                    onDrop={(kind, fl) => addFileFromInput(kind, fl)}
                    onDemoCase={id => void handleDemoCase(id)}
                    onBeginAnalysis={beginAnalysis}
                    onBack={goBack}
                    inputRefs={inputRefs}
                  />
                )}
              </div>
            </>
          )}
        </div>
      </main>
      <DreelioFooter />
    </div>
  )
}
