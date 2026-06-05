import { useEffect } from 'react'
import { createPortal } from 'react-dom'

type LeaveAnalysisDialogProps = {
  open: boolean
  onStay: () => void
  onLeave: () => void
}

export default function LeaveAnalysisDialog({ open, onStay, onLeave }: LeaveAnalysisDialogProps) {
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        background: 'rgba(0,0,0,0.4)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
        pointerEvents: 'auto',
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="leave-home-title"
      onClick={onStay}
    >
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          width: '100%',
          maxWidth: 440,
          borderRadius: 20,
          background: '#fff',
          border: '1px solid var(--line)',
          padding: 28,
          boxShadow: 'var(--sh-xl)',
          pointerEvents: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'flex-start' }}>
          <span className="material-symbols-outlined" style={{ color: '#d97706', fontSize: 28, flexShrink: 0 }}>
            warning
          </span>
          <div>
            <h2 id="leave-home-title" style={{ fontWeight: 800, fontSize: 17, color: 'var(--accent)', marginBottom: 8 }}>
              Leave and reset analysis?
            </h2>
            <p style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.65 }}>
              Going back to the home page will clear your current claim analysis, uploaded document
              context, and generated summaries from this session. You will need to run a new analysis
              to see results again.
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={onStay}
            style={{
              padding: '8px 18px',
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--ink)',
              background: 'transparent',
              border: '1.5px solid var(--line)',
              borderRadius: 999,
              cursor: 'pointer',
              pointerEvents: 'auto',
            }}
          >
            Stay on this page
          </button>
          <button
            type="button"
            onClick={onLeave}
            style={{
              padding: '8px 18px',
              fontSize: 13,
              fontWeight: 700,
              color: '#fff',
              background: 'var(--accent)',
              border: 'none',
              borderRadius: 999,
              cursor: 'pointer',
              pointerEvents: 'auto',
            }}
          >
            Leave & reset
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
