import { useEffect, useRef, useState } from 'react'
import type { ComponentType, CSSProperties, ReactNode, ElementType } from 'react'
import { useNavigate } from 'react-router-dom'
import '../styles/dreelio-landing.css'
import DreelioNav from '../components/marketing/DreelioNav'
import DreelioFooter from '../components/marketing/DreelioFooter'
import { DreelioThemeProvider, useDreelioThemeContext } from '../components/marketing/DreelioThemeContext'
import TransitionLink from '../components/marketing/TransitionLink'
import { viewTransitionNavigate } from '../lib/viewTransitionNavigate'

// ── Reveal component ──────────────────────────────────────────────────────────
interface RevealProps {
  children?: ReactNode
  delay?: number
  as?: string
  className?: string
  style?: CSSProperties
  id?: string
  href?: string
  [key: string]: unknown
}

function Reveal({ children, delay = 0, as: Tag = 'div', className = '', style, ...rest }: RevealProps) {
  const cls = ['reveal', className].filter(Boolean).join(' ')
  const C = Tag as ElementType
  return (
    <C
      className={cls}
      style={{ transitionDelay: delay ? `${delay}ms` : undefined, ...style }}
      {...rest}
    >
      {children}
    </C>
  )
}

// ── Reveal engine hook ────────────────────────────────────────────────────────
function useRevealEngine() {
  useEffect(() => {
    if ((window as any).__dlRevealActive) return

    function reveal(el: Element) {
      el.classList.add('is-in')
      setTimeout(() => {
        ;(el as HTMLElement).style.transition = 'none'
        ;(el as HTMLElement).style.opacity = '1'
        ;(el as HTMLElement).style.transform = 'none'
      }, 1000)
    }

    function sweep() {
      const vh = window.innerHeight || document.documentElement.clientHeight
      document.querySelectorAll('.dreelio-landing .reveal:not(.is-in)').forEach((el) => {
        const r = el.getBoundingClientRect()
        if (r.top < vh * 0.94 && r.bottom > 0) reveal(el)
      })
    }

    ;(window as any).__dlRevealActive = true
    window.addEventListener('scroll', sweep, { passive: true })
    window.addEventListener('resize', sweep)

    let n = 0
    const iv = setInterval(() => { sweep(); if (++n > 50) clearInterval(iv) }, 80)
    requestAnimationFrame(sweep)
    setTimeout(() => {
      document.querySelectorAll('.dreelio-landing .reveal:not(.is-in)').forEach(reveal)
    }, 3000)

    return () => {
      window.removeEventListener('scroll', sweep)
      window.removeEventListener('resize', sweep)
      clearInterval(iv)
      ;(window as any).__dlRevealActive = false
    }
  }, [])
}

// ── Scroll tilt hook ──────────────────────────────────────────────────────────
function useScrollTilt(maxTilt: number) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el || maxTilt === 0) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) { el.style.transform = 'none'; return }
    let raf = 0
    const update = () => {
      raf = 0
      const vh = window.innerHeight || 800
      const r = el.getBoundingClientRect()
      const start = vh * 0.9, end = vh * 0.3
      let p = (start - r.top) / (start - end)
      p = Math.max(0, Math.min(1, p))
      const tilt = maxTilt * (1 - p)
      const scale = 0.94 + 0.06 * p
      const lift = 28 * (1 - p)
      el.style.transform = `perspective(1800px) rotateX(${tilt.toFixed(2)}deg) scale(${scale.toFixed(3)}) translateY(${lift.toFixed(1)}px)`
    }
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update) }
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    update()
    const t = setTimeout(update, 200)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      cancelAnimationFrame(raf)
      clearTimeout(t)
    }
  }, [maxTilt])
  return ref
}

// ── Faux UI frames ────────────────────────────────────────────────────────────
function BrowserFrame({ children, url: _url = 'app.resolvly.com/action-plan' }: { children: ReactNode; url?: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: 16, overflow: 'hidden', border: '1px solid var(--line)', boxShadow: 'var(--sh-xl)' }}>
      <div style={{ height: 40, background: '#f4f1ea', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px' }}>
        <div style={{ display: 'flex', gap: 7 }}>
          {['#e6685f', '#f4bf4f', '#5ec26a'].map((c) => (
            <span key={c} style={{ width: 11, height: 11, borderRadius: '50%', background: c }} />
          ))}
        </div>
        <div style={{ flex: 1, maxWidth: 360, margin: '0 auto', background: '#fff', borderRadius: 7, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '0 10px', border: '1px solid var(--line)' }}>
          <span className="ms" style={{ fontSize: 12, color: '#5ec26a' }}>lock</span>
          <span style={{ width: 90, height: 6, borderRadius: 3, background: 'var(--line)' }} />
        </div>
        <div style={{ width: 52 }} />
      </div>
      <div style={{ background: '#f8f9fa' }}>{children}</div>
    </div>
  )
}

function PhoneFrame({ children }: { children: ReactNode }) {
  return (
    <div style={{ width: 300, maxWidth: '100%', background: '#14110b', borderRadius: 44, padding: 10, boxShadow: 'var(--sh-xl)' }}>
      <div style={{ background: '#f8f9fa', borderRadius: 36, overflow: 'hidden', position: 'relative', minHeight: 520 }}>
        <div style={{ position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)', width: 88, height: 24, background: '#14110b', borderRadius: 999, zIndex: 5 }} />
        {children}
      </div>
    </div>
  )
}

function Gauge({ pct = 62, size = 64, stroke = 6 }: { pct?: number; size?: number; stroke?: number }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  return (
    <div style={{ position: 'relative', width: size, height: size, flex: 'none' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e1e3e4" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#003461" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${(c * pct) / 100} ${c}`} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: size * 0.26, color: '#003461' }}>
        {pct}%
      </div>
    </div>
  )
}

function MiniPill({ children, bg = 'var(--amber-bg)', fg = 'var(--amber-ink)', icon }: { children: ReactNode; bg?: string; fg?: string; icon?: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: bg, color: fg, fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 999, letterSpacing: '0.01em' }}>
      {icon && <span className="ms fill" style={{ fontSize: 12 }}>{icon}</span>}
      {children}
    </span>
  )
}

function StatusTag({ ok }: { ok: boolean }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 7px', borderRadius: 4, background: ok ? 'var(--emerald-bg)' : 'var(--error-bg)', color: ok ? 'var(--emerald-ink)' : 'var(--error-ink)' }}>
      {ok ? 'Present' : 'Missing'}
    </span>
  )
}

const navy = '#003461', inkDark = '#191c1d', ink2 = '#424750'

function AppBar() {
  return (
    <div style={{ height: 46, borderBottom: '1px solid #eceef0', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 18px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <span style={{ fontWeight: 800, fontSize: 16, color: navy, letterSpacing: '-0.04em' }}>Resolvly</span>
        <div style={{ display: 'flex', gap: 14 }}>
          {['Analyze', 'Action Plan', 'Appeal'].map((t, i) => (
            <span key={t} style={{ fontSize: 12, fontWeight: i === 1 ? 700 : 500, color: i === 1 ? navy : ink2 }}>{t}</span>
          ))}
        </div>
      </div>
      <div style={{ width: 26, height: 26, borderRadius: 999, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: navy }}>SW</div>
    </div>
  )
}

// ── Faux screens ──────────────────────────────────────────────────────────────
function FauxDashboard() {
  return (
    <div style={{ fontFamily: 'var(--font)' }}>
      <AppBar />
      <div style={{ padding: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, marginBottom: 18 }}>
          <div>
            <MiniPill icon="priority_high">Time-Sensitive</MiniPill>
            <div style={{ fontSize: 26, fontWeight: 800, color: navy, letterSpacing: '-0.03em', marginTop: 8 }}>Action Plan &amp; Deadlines</div>
            <div style={{ fontSize: 12, color: ink2, marginTop: 2 }}>Claim #HM-2026-0041837 · Outpatient MRI (CPT 70553)</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, background: '#fff', border: '1px solid #eceef0', borderRadius: 14, padding: '12px 18px', boxShadow: 'var(--sh-sm)' }}>
            <Gauge pct={62} />
            <div>
              <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>Likelihood of Success</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: navy }}>Prior Authorization</div>
            </div>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: '#fff', border: '1px solid #eceef0', borderRadius: 14, padding: 18 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: navy, marginBottom: 8 }}>Denial summary</div>
              <p style={{ fontSize: 12, lineHeight: 1.6, color: inkDark, margin: 0 }}>
                Your insurer denied your outpatient MRI citing <strong style={{ color: navy }}>CO-197</strong> — "prior authorization not obtained." This is procedural, not a medical-necessity denial. Your provider can request a retroactive authorization, which frequently resolves it.
              </p>
            </div>
            <div style={{ background: '#f3f4f5', borderRadius: 14, padding: 18 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: navy, marginBottom: 14 }}>Recovery Roadmap</div>
              {[
                { n: 1, t: 'Request retroactive prior authorization', tag: 'Critical', active: true },
                { n: 2, t: 'File your internal appeal in writing', active: false },
                { n: 3, t: 'Escalate to IDOI external review if upheld', active: false },
              ].map((s) => (
                <div key={s.n} style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'flex-start' }}>
                  <div style={{ width: 26, height: 26, borderRadius: 999, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 12, background: s.active ? navy : '#e1e3e4', color: s.active ? '#fff' : ink2, boxShadow: s.active ? 'var(--sh-md)' : 'none' }}>{s.n}</div>
                  <div style={{ background: '#fff', border: '1px solid #eceef0', borderRadius: 10, padding: '10px 12px', flex: 1, opacity: s.active ? 1 : 0.82 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 700, color: inkDark }}>{s.t}</span>
                      {s.tag && <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: '#d3e4ff', color: '#001c38', whiteSpace: 'nowrap' }}>{s.tag}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: '#fff', border: '1px solid #eceef0', borderRadius: 14, padding: 18 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: navy, marginBottom: 14 }}>Critical Deadlines</div>
              {[
                { m: 'MAR', d: '14', l: 'Internal Appeal Window', s: '180 days from EOB receipt', hot: true },
                { m: 'JUN', d: '12', l: 'External review / IDOI', s: 'IDOI external review window', hot: false },
              ].map((x) => (
                <div key={x.m} style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center' }}>
                  <div style={{ width: 42, height: 48, borderRadius: 9, flex: 'none', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: x.hot ? 'var(--error-bg)' : '#eceef0' }}>
                    <span style={{ fontSize: 9, fontWeight: 700, color: x.hot ? 'var(--error-ink)' : ink2 }}>{x.m}</span>
                    <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1, color: x.hot ? 'var(--error-ink)' : ink2 }}>{x.d}</span>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: x.hot ? navy : ink2 }}>{x.l}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--ink-3)' }}>{x.s}</div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ background: '#fff', border: '1px solid #eceef0', borderRadius: 14, padding: 18 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: navy, marginBottom: 12 }}>Bill Breakdown</div>
              {[['Billed Amount', '$4,820', inkDark], ['Plan Paid', '$1,150', '#047857'], ['Denied (Disputed)', '$3,670', 'var(--error)']].map(([l, v, c]) => (
                <div key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f0f1f2', fontSize: 12, color: ink2 }}>
                  <span>{l}</span>
                  <span style={{ fontWeight: 800, color: c }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function FauxMobile() {
  const steps = [
    { n: 1, t: 'Retroactive prior auth', a: true },
    { n: 2, t: 'File internal appeal', a: false },
    { n: 3, t: 'IDOI external review', a: false },
  ]
  const gaugeR = 22
  const gaugeC = 2 * Math.PI * gaugeR

  return (
    <div style={{ fontFamily: 'var(--font)', display: 'flex', flexDirection: 'column', minHeight: 520 }}>
      <div style={{ height: 44, flexShrink: 0 }} aria-hidden />
      <div
        style={{
          padding: '0 14px 10px',
          borderBottom: '1px solid #eceef0',
          background: '#fff',
          flexShrink: 0,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 13, color: navy, letterSpacing: '-0.03em' }}>Resolvly</span>
      </div>

      <div style={{ padding: '14px 14px 18px', display: 'flex', flexDirection: 'column', gap: 12, flex: 1 }}>
        <div
          style={{
            background: navy,
            borderRadius: 14,
            padding: '12px 14px',
            color: '#fff',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#8abcff', marginBottom: 10 }}>
            Likelihood of success
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ position: 'relative', width: 48, height: 48, flexShrink: 0 }}>
              <svg width={48} height={48} style={{ transform: 'rotate(-90deg)', display: 'block' }}>
                <circle cx={24} cy={24} r={gaugeR} fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth={4} />
                <circle
                  cx={24}
                  cy={24}
                  r={gaugeR}
                  fill="none"
                  stroke="#8abcff"
                  strokeWidth={4}
                  strokeLinecap="round"
                  strokeDasharray={`${(gaugeC * 62) / 100} ${gaugeC}`}
                />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 13 }}>
                62%
              </div>
            </div>
            <p style={{ margin: 0, fontSize: 11, fontWeight: 500, lineHeight: 1.45, color: 'rgba(255,255,255,0.92)' }}>
              Prior auth denial — procedural and often reversible.
            </p>
          </div>
        </div>

        <div>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: ink2,
              marginBottom: 8,
            }}
          >
            Recovery roadmap
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {steps.map((s) => (
              <div
                key={s.n}
                style={{
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                  background: '#fff',
                  border: '1px solid #e8eaed',
                  borderRadius: 10,
                  padding: '8px 10px',
                }}
              >
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 999,
                    flex: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 600,
                    fontSize: 10,
                    background: s.a ? navy : '#eceef0',
                    color: s.a ? '#fff' : ink2,
                  }}
                >
                  {s.n}
                </div>
                <span style={{ fontSize: 11, fontWeight: 500, color: inkDark, lineHeight: 1.3 }}>{s.t}</span>
              </div>
            ))}
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            gap: 10,
            alignItems: 'center',
            background: 'var(--error-bg)',
            borderRadius: 10,
            padding: '9px 10px',
            marginTop: 'auto',
          }}
        >
          <div
            style={{
              width: 32,
              height: 36,
              borderRadius: 7,
              flex: 'none',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#fff',
            }}
          >
            <span style={{ fontSize: 7, fontWeight: 600, color: 'var(--error-ink)', letterSpacing: '0.04em' }}>MAR</span>
            <span style={{ fontSize: 14, fontWeight: 700, lineHeight: 1, color: 'var(--error-ink)' }}>14</span>
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--error-ink)', lineHeight: 1.25 }}>Internal appeal due</div>
            <div style={{ fontSize: 9.5, color: 'var(--error-ink)', opacity: 0.85, marginTop: 2, lineHeight: 1.35 }}>
              180 days from EOB receipt
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function FauxUpload() {
  const docs = [
    { t: 'Denial Letter', s: 'denial_HM-0041837.pdf', ok: true },
    { t: 'Explanation of Benefits', s: 'eob_2026-01.pdf', ok: true },
    { t: 'Medical Bill', s: 'Drop or browse to upload', ok: false },
  ]
  return (
    <div style={{ padding: 22, fontFamily: 'var(--font)' }}>
      <div style={{ fontSize: 18, fontWeight: 800, color: navy, letterSpacing: '-0.02em' }}>Upload &amp; Context</div>
      <p style={{ fontSize: 12, color: ink2, margin: '4px 0 18px' }}>We stitch your three documents into one coherent case.</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {docs.map((d) => (
          <div key={d.t} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: 14, borderRadius: 12, border: d.ok ? '1.5px solid #6ee7b7' : '1.5px dashed #c2c6d1', background: d.ok ? 'var(--emerald-bg)' : '#fff' }}>
            <span className="ms fill" style={{ fontSize: 26, color: d.ok ? 'var(--emerald)' : 'var(--ink-3)' }}>{d.ok ? 'task' : 'cloud_upload'}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: d.ok ? 'var(--emerald-ink)' : navy }}>{d.t}</div>
              <div style={{ fontSize: 11, color: d.ok ? 'var(--emerald-ink)' : 'var(--ink-3)', fontFamily: d.ok ? 'var(--mono)' : 'inherit', opacity: d.ok ? 0.85 : 1 }}>{d.s}</div>
            </div>
            {d.ok && <span className="ms fill" style={{ fontSize: 18, color: 'var(--emerald)' }}>check_circle</span>}
          </div>
        ))}
      </div>
      <button style={{ marginTop: 18, width: '100%', border: 'none', background: navy, color: '#fff', fontWeight: 700, fontSize: 13, padding: '13px', borderRadius: 999, fontFamily: 'var(--font)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
        Begin Forensic Analysis <span className="ms" style={{ fontSize: 16 }}>arrow_forward</span>
      </button>
    </div>
  )
}

function FauxPolicy() {
  const rows = [
    { f: 'Specific reason for denial', ok: true },
    { f: 'Clinical / scientific criteria', ok: false },
    { f: 'External review rights notice', ok: false },
    { f: 'State DOI complaint rights', ok: false },
    { f: 'Right-to-appeal statement', ok: true },
  ]
  return (
    <div style={{ padding: 22, fontFamily: 'var(--font)' }}>
      <div style={{ background: 'var(--accent-soft)', borderRadius: 14, padding: 16, marginBottom: 16, position: 'relative', overflow: 'hidden' }}>
        <span className="ms fill" style={{ position: 'absolute', right: -8, bottom: -14, fontSize: 78, color: 'rgba(0,52,97,0.10)' }}>gavel</span>
        <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent-soft-ink)' }}>Primary Regulatory Path</div>
        <div style={{ fontSize: 17, fontWeight: 800, color: navy, margin: '4px 0' }}>Indiana Dept. of Insurance</div>
        <p style={{ fontSize: 11.5, color: 'var(--accent-soft-ink)', margin: 0, lineHeight: 1.5, maxWidth: 280 }}>Fully-insured plans are state-regulated; IDOI administers external review under ACA §2719 and IC 27-4-1.</p>
      </div>
      <div style={{ fontSize: 13, fontWeight: 700, color: navy, marginBottom: 4 }}>Denial Notice Completeness</div>
      <div style={{ fontSize: 11, color: 'var(--ink-3)', marginBottom: 12 }}>Met 5 of 8 elements · ACA §2719 / ERISA §503</div>
      <div style={{ border: '1px solid #eceef0', borderRadius: 10, overflow: 'hidden' }}>
        {rows.map((r, i) => (
          <div key={r.f} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 12px', background: '#fff', borderTop: i ? '1px solid #f0f1f2' : 'none' }}>
            <span style={{ fontSize: 12, fontWeight: 500, color: inkDark }}>{r.f}</span>
            <StatusTag ok={r.ok} />
          </div>
        ))}
      </div>
    </div>
  )
}

function FauxDeadlines() {
  const days = Array.from({ length: 31 }, (_, i) => i + 1)
  return (
    <div style={{ padding: 22, fontFamily: 'var(--font)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ fontSize: 16, fontWeight: 800, color: navy }}>March 2026</div>
        <span style={{ fontSize: 11, fontWeight: 700, color: navy, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span className="ms" style={{ fontSize: 15 }}>calendar_add_on</span>.ics export
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 5 }}>
        {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
          <div key={i} style={{ textAlign: 'center', fontSize: 9, fontWeight: 700, color: 'var(--ink-3)', paddingBottom: 2 }}>{d}</div>
        ))}
        {Array.from({ length: 6 }).map((_, i) => <div key={'p' + i} />)}
        {days.map((d) => {
          const hot = d === 14
          return (
            <div key={d} style={{ aspectRatio: '1', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: hot ? 800 : 500, color: hot ? '#fff' : ink2, background: hot ? 'var(--error)' : '#fff', border: hot ? 'none' : '1px solid #f0f1f2' }}>
              {d}
            </div>
          )
        })}
      </div>
      <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 10, background: 'var(--error-bg)', borderRadius: 10, padding: '11px 13px' }}>
        <span className="ms fill" style={{ color: 'var(--error)', fontSize: 20 }}>notification_important</span>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--error-ink)' }}>Internal Appeal Window closes Mar 14</div>
          <div style={{ fontSize: 10.5, color: 'var(--error-ink)', opacity: 0.85 }}>180 days from EOB receipt · ACA §2719</div>
        </div>
      </div>
    </div>
  )
}

function FauxLetter() {
  return (
    <div style={{ padding: 22, fontFamily: 'var(--font)' }}>
      <div style={{ marginBottom: 10 }}>
        <MiniPill bg="var(--amber-bg)" fg="var(--amber-ink)" icon="warning">Draft — edit &amp; verify</MiniPill>
      </div>
      <div style={{ background: '#fff', border: '1px solid #eceef0', borderRadius: 12, padding: '18px 20px', boxShadow: 'var(--sh-sm)' }}>
        <div style={{ fontSize: 11, color: ink2, lineHeight: 1.6 }}>
          <div style={{ fontWeight: 700, color: inkDark }}>Sarah Whitfield</div>
          <div>Indianapolis, IN 46208</div>
          <div style={{ margin: '10px 0', color: 'var(--ink-3)' }}>Re: Internal Appeal — Claim #HM-2026-0041837</div>
          <p style={{ margin: '0 0 8px' }}>To the Appeals Review Committee:</p>
          <p style={{ margin: '0 0 8px' }}>I am writing to formally appeal the denial of coverage for an outpatient MRI <span style={{ background: '#fff7e6', borderRadius: 3, padding: '0 3px', fontWeight: 600, color: navy }}>(CPT 70553)</span>, denied under code <span style={{ background: '#fff7e6', borderRadius: 3, padding: '0 3px', fontWeight: 600, color: navy }}>CO-197</span>.</p>
          <p style={{ margin: 0 }}>Under <span style={{ background: 'var(--accent-soft)', borderRadius: 3, padding: '0 3px', fontWeight: 600, color: navy }}>ACA §2719</span> and <span style={{ background: 'var(--accent-soft)', borderRadius: 3, padding: '0 3px', fontWeight: 600, color: navy }}>45 CFR §147.136</span>, I am entitled to a full and fair internal review of the $3,670.00 in disputed charges…</p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button style={{ flex: 1, border: 'none', background: navy, color: '#fff', fontWeight: 700, fontSize: 12, padding: '11px', borderRadius: 999, fontFamily: 'var(--font)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <span className="ms" style={{ fontSize: 15 }}>picture_as_pdf</span>Export PDF
        </button>
        <button style={{ border: '1px solid var(--line-strong)', background: '#fff', color: navy, fontWeight: 700, fontSize: 12, padding: '11px 16px', borderRadius: 999, fontFamily: 'var(--font)' }}>Edit</button>
      </div>
    </div>
  )
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function DreelioHero({ variant = 'centered', onStart }: { variant?: 'centered' | 'split'; onStart: () => void }) {
  const tiltRef = useScrollTilt(variant === 'split' ? 0 : 9)

  const eyebrow = (
    <span className="eyebrow reveal">
      <span className="dot" /> Indiana-focused regulatory guidance
    </span>
  )
  const ctas = (
    <div className="reveal reveal-d3" style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
      <button className="btn btn-primary" style={{ padding: '15px 28px', fontSize: 16 }} onClick={onStart}>
        Start Free Analysis <span className="ms arrow" style={{ fontSize: 19 }}>arrow_forward</span>
      </button>
      <TransitionLink to="#pipeline" className="btn btn-ghost" style={{ padding: '15px 26px', fontSize: 16 }}>
        <span className="ms" style={{ fontSize: 19 }}>play_circle</span> See how it works
      </TransitionLink>
    </div>
  )
  if (variant === 'split') {
    return (
      <header id="top" className="section" style={{ paddingTop: 132, paddingBottom: 'clamp(48px,7vw,96px)' }}>
        <div className="wrap-wide">
          <div className="hero-split" style={{ display: 'grid', gridTemplateColumns: '1fr 1.05fr', gap: 56, alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 26, alignItems: 'flex-start' }}>
              {eyebrow}
              <h1 className="display reveal reveal-d1" style={{ color: 'var(--ink)', margin: 0 }}>
                Understand your insurance denial in <span style={{ color: 'var(--accent)' }}>plain english</span>.
              </h1>
              <p className="lead reveal reveal-d2" style={{ maxWidth: 560, margin: 0 }}>
                Helping Hoosiers navigate insurance denial complexity. Professional analysis, regulatory alignment, and guided appeal drafting — in under 20 seconds.
              </p>
              {ctas}
            </div>
            <Reveal delay={120} className="hero-art" style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', inset: '-6% -4%', background: 'radial-gradient(60% 60% at 70% 30%, rgba(0,52,97,0.10), transparent)', filter: 'blur(20px)' }} />
              <div style={{ position: 'relative', transform: 'perspective(1600px) rotateY(-7deg) rotateX(2deg)' }}>
                <BrowserFrame><FauxDashboard /></BrowserFrame>
              </div>
            </Reveal>
          </div>
        </div>
      </header>
    )
  }

  return (
    <header id="top" className="section" style={{ paddingTop: 148, paddingBottom: 'clamp(40px,6vw,80px)', textAlign: 'center' }}>
      <div className="wrap" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26 }}>
        {eyebrow}
        <h1 className="display reveal reveal-d1" style={{ color: 'var(--ink)', maxWidth: 1000, margin: 0 }}>
          Understand your insurance denial in <span style={{ color: 'var(--accent)' }}>plain english</span>.
        </h1>
        <p className="lead reveal reveal-d2" style={{ maxWidth: 620, textAlign: 'center', margin: 0 }}>
          Helping Hoosiers navigate insurance denial complexity. Professional analysis, regulatory alignment, and guided appeal drafting — in under 20 seconds.
        </p>
        {ctas}
      </div>
      <Reveal delay={180} className="wrap-wide hero-art" style={{ marginTop: 56, position: 'relative' }}>
        <div style={{ position: 'absolute', inset: '-4% 6% 8%', background: 'radial-gradient(50% 50% at 50% 0%, rgba(0,52,97,0.12), transparent)', filter: 'blur(24px)' }} />
        <div ref={tiltRef} style={{ position: 'relative', maxWidth: 1040, margin: '0 auto', transformOrigin: 'center top', willChange: 'transform' }}>
          <BrowserFrame><FauxDashboard /></BrowserFrame>
        </div>
      </Reveal>
    </header>
  )
}

// ── Trust Marquee ─────────────────────────────────────────────────────────────
const SOURCES = ['CMS.gov', 'NPPES', 'WPC EDI Codes', 'Indiana DOI', 'ACA §2719', 'ERISA §503', 'Medicaid.gov', '45 CFR §147', 'IC 27-4-1']
const SOURCE_ICONS = ['account_balance', 'verified', 'database', 'gavel', 'policy', 'shield', 'local_hospital', 'fact_check', 'balance']

function TrustMarquee() {
  const row = SOURCES.concat(SOURCES)
  return (
    <section id="trust" className="section-tight" style={{ borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', background: 'var(--canvas-soft)' }}>
      <div className="wrap">
        <Reveal style={{ textAlign: 'center', marginBottom: 30 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-3)', letterSpacing: '0.04em' }}>
            Every code and citation checked against authoritative federal &amp; state sources
          </span>
        </Reveal>
      </div>
      <div className="marquee" style={{ '--mq-dur': '42s' } as CSSProperties}>
        <div className="marquee-track" style={{ gap: 0 }}>
          {row.map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 38px', whiteSpace: 'nowrap' }}>
              <span className="ms" style={{ fontSize: 20, color: 'var(--accent)', opacity: 0.55 }}>{SOURCE_ICONS[i % 9]}</span>
              <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink)', opacity: 0.55, letterSpacing: '-0.02em' }}>{s}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Devices ───────────────────────────────────────────────────────────────────
function Devices() {
  const [view, setView] = useState<'web' | 'mobile'>('web')
  const stageRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = stageRef.current
    if (!el) return
    const t = setTimeout(() => {
      el.style.animation = 'none'
      el.style.opacity = '1'
      el.style.transform = 'none'
    }, 480)
    return () => clearTimeout(t)
  }, [view])

  const options: Array<{ id: 'web' | 'mobile'; label: string; icon: string }> = [
    { id: 'web', label: 'Web App', icon: 'desktop_windows' },
    { id: 'mobile', label: 'Mobile App', icon: 'smartphone' },
  ]

  return (
    <section className="section">
      <div className="wrap">
        <div style={{ textAlign: 'center', maxWidth: 640, margin: '0 auto 36px' }}>
          <Reveal as="h2" className="h-xl reveal-d1" style={{ color: 'var(--ink)', margin: '0 0 16px' }}>
            Track your appeal from desk or<br />pocket — always in sync
          </Reveal>
          <Reveal as="p" className="lead reveal-d2" style={{ margin: 0 }}>
            The full forensic analysis on the web, a calm at-a-glance plan on mobile. Pick up exactly where you left off.
          </Reveal>
        </div>

        <Reveal delay={60} style={{ display: 'flex', justifyContent: 'center', marginBottom: 36 }}>
          <div style={{ position: 'relative', display: 'inline-flex', padding: 5, gap: 4, background: 'var(--card)', border: '1px solid var(--line)', borderRadius: 'var(--r-pill)', boxShadow: 'var(--sh-sm)' }}>
            <div style={{ position: 'absolute', top: 5, bottom: 5, width: 'calc(50% - 5px)', left: view === 'web' ? 5 : 'calc(50%)', background: 'var(--accent)', borderRadius: 'var(--r-pill)', transition: 'left .4s var(--ease)', boxShadow: 'var(--sh-md)' }} />
            {options.map((o) => {
              const on = view === o.id
              return (
                <button key={o.id} onClick={() => setView(o.id)} style={{ position: 'relative', zIndex: 1, display: 'inline-flex', alignItems: 'center', gap: 8, padding: '11px 24px', borderRadius: 'var(--r-pill)', border: 'none', cursor: 'pointer', background: 'transparent', fontFamily: 'var(--font)', fontSize: 15, fontWeight: 600, color: on ? '#fff' : 'var(--ink-2)', transition: 'color .3s var(--ease)', whiteSpace: 'nowrap' }}>
                  <span className={on ? 'ms fill' : 'ms'} style={{ fontSize: 19 }}>{o.icon}</span>{o.label}
                </button>
              )
            })}
          </div>
        </Reveal>

        <Reveal delay={120} style={{ position: 'relative', borderRadius: 'var(--r-xl)', background: 'linear-gradient(160deg, #f4eee3, #e7dfcf)', border: '1px solid var(--line)', padding: 'clamp(28px,5vw,64px)', overflow: 'hidden' }}>
          <span className="ms" style={{ position: 'absolute', top: -30, right: -20, fontSize: 200, color: 'rgba(0,52,97,0.04)' }}>sync</span>
          <div style={{ position: 'relative', minHeight: 480, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div
              key={view}
              ref={stageRef}
              className="device-swap"
              style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}
            >
              {view === 'web' ? (
                <div style={{ width: '100%', maxWidth: 820 }}>
                  <BrowserFrame url="app.resolvly.com/action-plan"><FauxDashboard /></BrowserFrame>
                </div>
              ) : (
                <PhoneFrame><FauxMobile /></PhoneFrame>
              )}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}

// ── Feature Tabs (Pipeline) ───────────────────────────────────────────────────
interface PipelineCard {
  id: string
  label: string
  icon: string
  title: string
  desc: string
  Screen: ComponentType
}

function FeatureTabs() {
  const CARDS: PipelineCard[] = [
    { id: 'stitch', label: 'Multi-Doc Stitching', icon: 'auto_awesome_motion', title: 'Three documents, one coherent case', desc: 'Upload your denial letter, EOB, and medical bill. Resolvly stitches them into a single timeline — matching codes, dates, and dollar amounts across every page.', Screen: FauxUpload },
    { id: 'policy', label: 'Policy Intelligence', icon: 'gavel', title: 'The exact regulation, routed to you', desc: 'We detect your plan type and route the appeal correctly — ERISA, ACA, or Medicaid — then score the denial notice against every element the law requires.', Screen: FauxPolicy },
    { id: 'deadline', label: 'Deadline Calculus', icon: 'event_available', title: 'Never miss the window that matters', desc: 'Every appeal deadline calculated from your documents and exported to your calendar as an .ics file — so the 180-day clock never runs out unnoticed.', Screen: FauxDeadlines },
    { id: 'appeal', label: 'Appeal Drafting', icon: 'edit_document', title: 'A formal appeal, citations included', desc: 'Resolvly drafts a ready-to-send appeal letter citing the regulations that apply to your case. Every draft is yours to review and verify before it goes out.', Screen: FauxLetter },
  ]
  const N = CARDS.length
  const [active, setActive] = useState(0)
  const [progress, setProgress] = useState(0)
  const scrollerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const scroller = scrollerRef.current
    if (!scroller) return
    let raf = 0
    const update = () => {
      raf = 0
      if (window.innerWidth <= 980) { setProgress(0); setActive(0); return }
      const vh = window.innerHeight || 800
      const total = scroller.offsetHeight - vh
      const top = scroller.getBoundingClientRect().top
      const p = total > 0 ? Math.min(1, Math.max(0, -top / total)) : 0
      setProgress(p)
      setActive(Math.min(N - 1, Math.floor(p * N + 0.0001)))
    }
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update) }
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    update()
    const t = setTimeout(update, 250)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      cancelAnimationFrame(raf)
      clearTimeout(t)
    }
  }, [N])

  const goToStep = (i: number) => {
    const scroller = scrollerRef.current
    if (!scroller || window.innerWidth <= 980) { setActive(i); return }
    const vh = window.innerHeight || 800
    const total = scroller.offsetHeight - vh
    const top = scroller.offsetTop + ((i + 0.5) / N) * total
    window.scrollTo({ top, behavior: 'smooth' })
  }

  const T = CARDS[active]
  const railFill = `${Math.min(100, Math.max(100 / N / 2, progress * 100))}%`

  const deckStyle = (i: number): CSSProperties => {
    const d = i - active
    if (d < 0) return { transform: 'translateY(-114%) scale(1.01)', opacity: 0, visibility: 'hidden', zIndex: 1, pointerEvents: 'none' }
    return {
      transform: `translateY(${d * 16}px) scale(${(1 - d * 0.04).toFixed(3)})`,
      opacity: d > 2 ? 0 : 1,
      visibility: d > 2 ? 'hidden' : 'visible',
      zIndex: 30 - d,
      filter: d > 0 ? `brightness(${(1 - d * 0.05).toFixed(3)})` : 'none',
    }
  }

  return (
    <section id="pipeline" style={{ background: 'var(--canvas-soft)', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)' }}>
      <div className="wrap-wide" style={{ paddingTop: 'clamp(72px,10vw,128px)' }}>
        <div style={{ textAlign: 'center', maxWidth: 680, margin: '0 auto' }}>
          <Reveal as="h2" className="h-xl reveal-d1" style={{ color: 'var(--ink)', margin: '0 0 16px' }}>The Proprietary Resolution Pipeline</Reveal>
          <Reveal as="p" className="lead reveal-d2" style={{ margin: 0 }}>A multi-agent forensic engine turns an opaque denial into an action plan, a deadline calendar, and a finished appeal. Scroll to step through each stage.</Reveal>
        </div>
      </div>

      <div ref={scrollerRef} className="pipeline-scroller" style={{ position: 'relative', height: `calc(100vh + ${(N - 1) * 60}vh)` }}>
        <div className="pipeline-sticky" style={{ position: 'sticky', top: 0, minHeight: '100vh', display: 'flex', alignItems: 'center' }}>
          <div className="wrap-wide" style={{ width: '100%', paddingTop: 24, paddingBottom: 24 }}>
            <div className="card tabs-card" style={{ display: 'grid', gridTemplateColumns: '0.9fr 1.1fr', gap: 0, overflow: 'hidden', borderRadius: 'var(--r-xl)', boxShadow: 'var(--sh-lg)' }}>
              {/* Left — step rail */}
              <div style={{ padding: 'clamp(24px,3vw,40px)', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>The pipeline</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: 'var(--accent)' }}>{String(active + 1).padStart(2, '0')} / {String(N).padStart(2, '0')}</span>
                </div>
                <div style={{ position: 'relative' }}>
                  <div style={{ position: 'absolute', left: 18, top: 18, bottom: 18, width: 2, background: 'var(--line-strong)', borderRadius: 2 }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: railFill, background: 'var(--accent)', borderRadius: 2, transition: 'height .15s linear' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {CARDS.map((c, i) => {
                      const on = i === active, done = i < active
                      return (
                        <button key={c.id} onClick={() => goToStep(i)} style={{ display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left', cursor: 'pointer', padding: '12px 14px 12px 0', borderRadius: 'var(--r-md)', fontFamily: 'var(--font)', border: 'none', background: 'transparent', position: 'relative' }}>
                          <span style={{ width: 38, height: 38, flex: 'none', borderRadius: 999, zIndex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: (on || done) ? 'var(--accent)' : 'var(--card-pure)', color: (on || done) ? '#fff' : 'var(--accent)', border: '2px solid ' + ((on || done) ? 'var(--accent)' : 'var(--line-strong)'), boxShadow: on ? '0 0 0 5px var(--accent-tint)' : 'none', transition: 'all .3s var(--ease)', transform: on ? 'scale(1.06)' : 'scale(1)' }}>
                            <span className={(on || done) ? 'ms fill' : 'ms'} style={{ fontSize: 20 }}>{done ? 'check' : c.icon}</span>
                          </span>
                          <span style={{ fontSize: 16, fontWeight: on ? 700 : 600, color: on ? 'var(--ink)' : done ? 'var(--ink-2)' : 'var(--ink-3)', transition: 'color .3s var(--ease)' }}>{c.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
                <div key={T.id} className="tab-copy" style={{ marginTop: 26, paddingTop: 24, borderTop: '1px solid var(--line)' }}>
                  <h3 className="h-lg" style={{ color: 'var(--accent)', margin: '0 0 12px', fontSize: 24 }}>{T.title}</h3>
                  <p className="body" style={{ margin: 0 }}>{T.desc}</p>
                </div>
              </div>
              {/* Right — screenshot deck */}
              <div style={{ background: 'linear-gradient(160deg, #eef2f4, #e3e9ec)', padding: 'clamp(24px,3vw,44px)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderLeft: '1px solid var(--line)' }}>
                <div className="deck" style={{ position: 'relative', width: '100%', maxWidth: 520, height: 'min(70vh, 560px)' }}>
                  {CARDS.map((c, i) => {
                    const Screen = c.Screen
                    return (
                      <div key={c.id} className="deck-card" style={{ position: 'absolute', top: 0, left: 0, right: 0, transformOrigin: 'center top', ...deckStyle(i) }}>
                        <BrowserFrame><Screen /></BrowserFrame>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
            <div className="pipeline-hint" style={{ display: 'flex', justifyContent: 'center', marginTop: 18, gap: 8, alignItems: 'center', color: 'var(--ink-3)', fontSize: 13, fontWeight: 600 }}>
              <span className="ms" style={{ fontSize: 18 }}>keyboard_double_arrow_down</span>
              Scroll to advance through the pipeline
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Feature Grid ──────────────────────────────────────────────────────────────
function SourceLogo({ icon, label }: { icon: string; label: string }) {
  return (
    <div className="card-hover" style={{ aspectRatio: '1.6', borderRadius: 'var(--r-md)', background: 'var(--card-pure)', border: '1px solid var(--line)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
      <span className="ms" style={{ fontSize: 24, color: 'var(--accent)' }}>{icon}</span>
      <span style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--ink-2)', letterSpacing: '-0.01em' }}>{label}</span>
    </div>
  )
}

function FeatureGrid() {
  const sources = [
    { icon: 'account_balance', label: 'CMS.gov' }, { icon: 'badge', label: 'NPPES' },
    { icon: 'database', label: 'WPC Codes' }, { icon: 'gavel', label: 'Indiana DOI' },
    { icon: 'local_hospital', label: 'Medicaid' }, { icon: 'policy', label: 'ACA §2719' },
    { icon: 'shield', label: 'ERISA §503' }, { icon: 'fact_check', label: '45 CFR §147' },
  ]
  const small = [
    { icon: 'stethoscope', title: 'Your doctor gets a brief too', desc: 'A concise clinical brief your physician can act on — generated alongside your appeal, ready to forward.' },
    { icon: 'translate', title: 'No jargon. Ever.', desc: 'CO-197, CPT codes, and statute citations decoded into plain English — so you know exactly what to do next.' },
    { icon: 'view_kanban', title: 'Every view you need', desc: 'Roadmap, deadline calendar, completeness checklist — the same case, shown the way that helps you most.' },
  ]

  return (
    <section id="features" className="section">
      <div className="wrap-wide">
        <div style={{ textAlign: 'center', maxWidth: 680, margin: '0 auto 56px' }}>
          <Reveal as="h2" className="h-xl reveal-d1" style={{ color: 'var(--ink)', margin: '0 0 16px' }}>Why Resolvly?</Reveal>
          <Reveal as="p" className="lead reveal-d2" style={{ margin: 0 }}>Other tools leave you with information. Resolvly gives you a complete action plan — codes decoded, deadlines set, appeal drafted.</Reveal>
        </div>

        <div className="bento-top" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
          <Reveal className="card card-hover" style={{ padding: 'clamp(24px,3vw,40px)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: 320 }}>
            <div>
              <h3 className="h-lg" style={{ color: 'var(--ink)', margin: '0 0 10px' }}>Because denial codes shouldn't stop you</h3>
              <p className="body" style={{ margin: 0, maxWidth: 380 }}>Resolvly reads the codes most patients give up on — and turns them into a plain-English action plan you can act on today.</p>
            </div>
            <div style={{ marginTop: 28, display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 15, fontWeight: 700, color: 'var(--error)', background: 'var(--error-bg)', padding: '8px 14px', borderRadius: 10 }}>CO-197</span>
              <span className="ms" style={{ fontSize: 26, color: 'var(--ink-3)' }}>arrow_forward</span>
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--accent)', background: 'var(--accent-soft)', padding: '8px 14px', borderRadius: 10, flex: 1, minWidth: 200 }}>"Prior authorization not obtained" — procedural, often reversible.</span>
            </div>
          </Reveal>

          <Reveal delay={100} className="card" style={{ padding: 'clamp(24px,3vw,40px)' }}>
            <h3 className="h-lg" style={{ color: 'var(--ink)', margin: '0 0 6px' }}>Accuracy you can cite in court</h3>
            <p className="body" style={{ margin: '0 0 22px', maxWidth: 380 }}>Every code and citation is verified against authoritative federal and Indiana databases — not a model's memory.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
              {sources.map((s) => <SourceLogo key={s.label} {...s} />)}
            </div>
          </Reveal>
        </div>

        <div className="bento-bottom" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 24 }}>
          {small.map((c, i) => (
            <Reveal key={c.title} delay={i * 90} className="card card-hover" style={{ padding: 30 }}>
              <span style={{ width: 46, height: 46, borderRadius: 13, background: 'var(--accent-tint)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18 }}>
                <span className="ms" style={{ fontSize: 24, color: 'var(--accent)' }}>{c.icon}</span>
              </span>
              <h4 style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: '0 0 8px', letterSpacing: '-0.02em' }}>{c.title}</h4>
              <p className="body" style={{ margin: 0, fontSize: 14.5 }}>{c.desc}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── CTA Banner ────────────────────────────────────────────────────────────────
function CTABanner({ onStart }: { onStart: () => void }) {
  return (
    <section className="section">
      <div className="wrap-wide">
        <Reveal style={{ position: 'relative', borderRadius: 'var(--r-xl)', background: 'linear-gradient(150deg, #003461, #00253f)', overflow: 'hidden', padding: 'clamp(40px,6vw,72px)' }}>
          <span className="ms" style={{ position: 'absolute', left: -30, bottom: -40, fontSize: 240, color: 'rgba(255,255,255,0.05)' }}>balance</span>
          <div className="cta-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48, alignItems: 'center', position: 'relative' }}>
            <div>
              <h2 className="h-xl" style={{ color: '#fff', margin: '0 0 16px' }}>Ready to push back?</h2>
              <p className="lead" style={{ color: '#b8d4ec', maxWidth: 440, margin: '0 0 28px' }}>
                Upload three documents you already have. Get a plain-English action plan, your deadlines, and a draft appeal — in under 20 seconds. No card required.
              </p>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <button className="btn btn-on-dark" style={{ padding: '15px 28px', fontSize: 16 }} onClick={onStart}>
                  Start Free Analysis <span className="ms arrow" style={{ fontSize: 19 }}>arrow_forward</span>
                </button>
                <TransitionLink to="#pipeline" className="btn btn-light" style={{ padding: '15px 26px', fontSize: 16 }}>
                  See how it works
                </TransitionLink>
              </div>
              <div style={{ marginTop: 24, fontSize: 13, color: '#8abcff', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="ms fill" style={{ fontSize: 17 }}>lock</span> Empowering every Hoosier with the tools to push back.
              </div>
            </div>
            <div style={{ position: 'relative' }}>
              <div style={{ transform: 'perspective(1400px) rotateY(-8deg)', borderRadius: 16, overflow: 'hidden', boxShadow: 'var(--sh-navy)' }}>
                <BrowserFrame url="app.resolvly.com/action-plan"><FauxDashboard /></BrowserFrame>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
function LandingPageContent() {
  const navigate = useNavigate()
  const goToAnalyze = () => viewTransitionNavigate(navigate, '/analyze')
  const { isDark } = useDreelioThemeContext()

  useRevealEngine()

  useEffect(() => {
    const prev = document.body.style.backgroundColor
    document.body.style.backgroundColor = isDark ? '#12100c' : '#efe8db'
    return () => {
      document.body.style.backgroundColor = prev
    }
  }, [isDark])

  return (
    <div
      className={`dreelio-landing${isDark ? ' dreelio-dark' : ''}`}
      style={{
        minHeight: '100vh',
        background: 'var(--canvas)',
        color: 'var(--ink)',
        fontFamily: 'var(--font)',
        WebkitFontSmoothing: 'antialiased',
        transition: 'background-color .35s var(--ease), color .35s var(--ease)',
      }}
    >
      <DreelioNav onStart={goToAnalyze} activePath="home" />
      <main>
        <DreelioHero variant="centered" onStart={goToAnalyze} />
        <TrustMarquee />
        <Devices />
        <FeatureTabs />
        <FeatureGrid />
        <CTABanner onStart={goToAnalyze} />
      </main>
      <DreelioFooter />
    </div>
  )
}

export default function LandingPage() {
  return (
    <DreelioThemeProvider>
      <LandingPageContent />
    </DreelioThemeProvider>
  )
}
